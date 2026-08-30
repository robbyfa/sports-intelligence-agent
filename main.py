"""CLI entry point for the Streaming Sports Intelligence Agent.

Loads a fixture match, ingests it into both stores, configures the tools,
and runs the LangGraph agent with sample questions, displaying structured output.
"""

from dotenv import load_dotenv

load_dotenv()

from fixtures import load_fixture
from graph.tools import configure
from storage.event_store import EventStore
from storage.vector_store import SportVectorStore
from streaming.pipeline import IngestionPipeline


def render_structured_response(result: dict) -> None:
    """Pretty-print a structured analysis response to the terminal."""
    sr = result.get("structured_response", {})

    # Answer
    answer = sr.get("answer", result.get("generation", "No answer generated."))
    print(f"\nAnswer:\n{answer}")

    # Evidence
    evidence = sr.get("evidence", [])
    if evidence:
        print("\nEvidence:")
        for e in evidence:
            player_tag = f" ({e.get('player', '')})" if e.get("player") else ""
            print(f"  - {e.get('minute', '?')}'{player_tag}: {e.get('description', '')}")

    # Confidence
    confidence = sr.get("confidence", "unknown")
    print(f"\nConfidence: {confidence}")

    # Sources
    sources = sr.get("sources", [])
    if sources:
        print(f"Sources: {', '.join(sources)}")

    # Retrieval provenance
    provenance = result.get("sources", [])
    if provenance:
        tool_sources = [s for s in provenance if s.get("type") == "tool_result"]
        vector_sources = [s for s in provenance if s.get("type") == "vector_search"]
        if tool_sources:
            tools_used = [s.get("tool", "?") for s in tool_sources]
            print(f"Tools called: {', '.join(tools_used)}")
        if vector_sources:
            print(f"Vector search hits: {len(vector_sources)}")


def main():
    print("Streaming Sports Intelligence Agent")
    print("=" * 50)

    # 1. Set up stores
    print("\n[1] Setting up stores...")
    event_store = EventStore("./data/sports.db")
    vector_store = SportVectorStore(
        collection_name="sports-events",
        persist_directory="./data/chroma",
    )

    # 2. Ingest fixture match
    print("[2] Ingesting match data...")
    feed = load_fixture("match_001")
    pipeline = IngestionPipeline(event_store, vector_store)
    count = pipeline.ingest_match(feed)
    print(f"    Ingested {count} events for {feed.metadata.home_team.name} vs {feed.metadata.away_team.name}")

    # 3. Configure tools with store instances
    print("[3] Configuring agent tools...")
    configure(event_store=event_store, vector_store=vector_store)

    # 4. Build and run the agent
    print("[4] Building agent graph...")
    from graph.graph import build_graph

    app = build_graph()

    # 5. Ask questions
    questions = [
        "What changed after the substitution?",
        "Summarise the match so far.",
        "Which player had the biggest impact?",
        "What are the key tactical shifts?",
        "Generate a post-match analyst brief.",
    ]

    for question in questions:
        print(f"\n{'=' * 60}")
        print(f"Q: {question}")
        print("-" * 60)

        result = app.invoke(
            input={
                "question": question,
                "match_id": "match_001",
                "retries": 0,
            }
        )

        render_structured_response(result)


if __name__ == "__main__":
    main()
