"""Run evaluations against the sports intelligence agent.

Usage:
    # Run all 20 questions
    python -m evals.run_evals

    # Run a specific category
    python -m evals.run_evals --category narrative

    # Run a specific question
    python -m evals.run_evals --question q01

    # Run with LangSmith tracing enabled
    LANGCHAIN_TRACING_V2=true python -m evals.run_evals

Environment variables for LangSmith tracing:
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=ls-...
    LANGCHAIN_PROJECT=sports-intelligence-evals
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

# Enable LangSmith tracing if API key is available
if os.getenv("LANGCHAIN_API_KEY"):
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "sports-intelligence-evals")

from evals.dataset import EVAL_DATASET, get_by_category
from evals.evaluators import evaluate_response
from fixtures import load_fixture
from graph.chains.router import question_router
from graph.graph import build_graph
from graph.tools import configure
from storage.event_store import EventStore
from storage.vector_store import SportVectorStore
from streaming.pipeline import IngestionPipeline


def setup() -> tuple:
    """Set up stores, ingest fixture, configure tools, build graph."""
    print("Setting up evaluation environment...")
    es = EventStore(":memory:")
    vs = SportVectorStore(collection_name="eval-store")

    feed = load_fixture("match_001")
    pipeline = IngestionPipeline(es, vs)
    pipeline.ingest_match(feed)

    configure(event_store=es, vector_store=vs)
    app = build_graph()

    print(f"  Ingested {len(feed.events)} events")
    return app, es, vs


def run_single(app, question_data: dict) -> dict:
    """Run a single evaluation question and return results."""
    question = question_data["question"]
    qid = question_data["id"]

    print(f"\n{'='*60}")
    print(f"[{qid}] {question}")
    print(f"  Expected route: {question_data['expected_route']}")

    # Detect actual route
    try:
        route_result = question_router.invoke({"question": question})
        actual_route = route_result.datasource
    except Exception:
        actual_route = "unknown"

    print(f"  Actual route:   {actual_route}")

    # Run the agent
    start_time = time.time()
    result = app.invoke(
        input={
            "question": question,
            "match_id": "match_001",
            "retries": 0,
        }
    )
    elapsed = time.time() - start_time

    # Get the answer
    sr = result.get("structured_response", {})
    answer = sr.get("answer", result.get("generation", ""))

    # Run evaluators
    scores = evaluate_response(
        question=question,
        result=result,
        expected=question_data,
        actual_route=actual_route,
    )

    # Print results
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Answer: {answer[:120]}...")
    print(f"  Scores:")
    for dim, score_data in scores.items():
        emoji = "✓" if score_data["score"] >= 0.7 else "△" if score_data["score"] >= 0.4 else "✗"
        print(f"    {emoji} {dim}: {score_data['score']:.2f} — {score_data['reasoning'][:80]}")

    return {
        "id": qid,
        "question": question,
        "category": question_data["category"],
        "expected_route": question_data["expected_route"],
        "actual_route": actual_route,
        "answer": answer,
        "scores": scores,
        "elapsed_seconds": round(elapsed, 1),
        "evidence_count": len(sr.get("evidence", [])),
        "confidence": sr.get("confidence", "unknown"),
    }


def print_summary(results: list[dict]) -> None:
    """Print a summary table of all evaluation results."""
    print(f"\n{'='*80}")
    print("EVALUATION SUMMARY")
    print(f"{'='*80}")

    dimensions = [
        "retrieval_relevance", "groundedness", "citation_quality",
        "tool_selection", "event_freshness", "overall",
    ]

    # Per-question scores
    print(f"\n{'ID':<5} {'Category':<16} {'Route':<6} {'Overall':<8} {'Ground':<8} {'Cite':<8} {'Tool':<8} {'Fresh':<8}")
    print("-" * 80)

    for r in results:
        s = r["scores"]
        route_ok = "✓" if r["actual_route"] == r["expected_route"] else "✗"
        print(
            f"{r['id']:<5} {r['category']:<16} {route_ok:<6} "
            f"{s['overall']['score']:<8.2f} "
            f"{s['groundedness']['score']:<8.2f} "
            f"{s['citation_quality']['score']:<8.2f} "
            f"{s['tool_selection']['score']:<8.2f} "
            f"{s['event_freshness']['score']:<8.2f}"
        )

    # Aggregate scores
    print(f"\n{'='*80}")
    print("AGGREGATE SCORES")
    print(f"{'='*80}")

    for dim in dimensions:
        scores = [r["scores"][dim]["score"] for r in results]
        avg = sum(scores) / len(scores) if scores else 0
        min_s = min(scores) if scores else 0
        max_s = max(scores) if scores else 0
        print(f"  {dim:<25} avg={avg:.3f}  min={min_s:.2f}  max={max_s:.2f}")

    # Category breakdown
    print(f"\n{'='*80}")
    print("CATEGORY BREAKDOWN")
    print(f"{'='*80}")

    categories = sorted(set(r["category"] for r in results))
    for cat in categories:
        cat_results = [r for r in results if r["category"] == cat]
        avg_overall = sum(r["scores"]["overall"]["score"] for r in cat_results) / len(cat_results)
        route_accuracy = sum(
            1 for r in cat_results if r["actual_route"] == r["expected_route"]
        ) / len(cat_results)
        print(f"  {cat:<20} n={len(cat_results)}  avg_overall={avg_overall:.3f}  route_accuracy={route_accuracy:.0%}")

    # Route accuracy
    total = len(results)
    correct_routes = sum(1 for r in results if r["actual_route"] == r["expected_route"])
    print(f"\n  Route accuracy: {correct_routes}/{total} ({correct_routes/total:.0%})")

    # Overall
    overall_avg = sum(r["scores"]["overall"]["score"] for r in results) / len(results)
    print(f"  Overall average score: {overall_avg:.3f}")
    print(f"  Total eval time: {sum(r['elapsed_seconds'] for r in results):.0f}s")


def main():
    parser = argparse.ArgumentParser(description="Run agent evaluations")
    parser.add_argument("--category", type=str, help="Filter by category")
    parser.add_argument("--question", type=str, help="Run a single question by ID")
    parser.add_argument("--output", type=str, help="Save results to JSON file")
    args = parser.parse_args()

    app, es, vs = setup()

    # Filter dataset
    dataset = EVAL_DATASET
    if args.category:
        dataset = get_by_category(args.category)
        print(f"Filtered to {len(dataset)} questions in category '{args.category}'")
    if args.question:
        dataset = [q for q in dataset if q["id"] == args.question]
        if not dataset:
            print(f"Question '{args.question}' not found")
            sys.exit(1)

    print(f"\nRunning {len(dataset)} evaluations...")

    results = []
    for q in dataset:
        try:
            result = run_single(app, q)
            results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "id": q["id"],
                "question": q["question"],
                "category": q["category"],
                "expected_route": q["expected_route"],
                "actual_route": "error",
                "answer": f"Error: {e}",
                "scores": {
                    dim: {"score": 0.0, "reasoning": f"Error: {e}"}
                    for dim in [
                        "retrieval_relevance", "groundedness", "citation_quality",
                        "tool_selection", "event_freshness", "overall",
                    ]
                },
                "elapsed_seconds": 0,
                "evidence_count": 0,
                "confidence": "error",
            })

    print_summary(results)

    # Save results if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to {args.output}")

    # Cleanup
    vs.reset()
    es.close()


if __name__ == "__main__":
    main()
