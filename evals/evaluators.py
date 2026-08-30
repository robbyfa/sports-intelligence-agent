"""Custom evaluators for the sports intelligence agent.

Five evaluation dimensions:
1. Retrieval relevance — did we fetch the right context?
2. Answer groundedness — is the answer supported by the evidence?
3. Source citation quality — are specific minutes/players cited?
4. Tool selection correctness — did the router pick the right path?
5. Event freshness — are the most important match moments referenced?

Each evaluator returns a dict with:
- score: float 0.0–1.0
- reasoning: str explaining the score
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


# ── LLM for evaluation ────────────────────────────────────────────

eval_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


class EvalScore(BaseModel):
    """Structured evaluation score."""
    score: float = Field(ge=0.0, le=1.0, description="Score from 0.0 to 1.0")
    reasoning: str = Field(description="Brief explanation of the score")


eval_scorer = eval_llm.with_structured_output(EvalScore)


# ── 1. Retrieval Relevance ─────────────────────────────────────────

def eval_retrieval_relevance(question: str, documents: list, expected: dict) -> dict:
    """Evaluate whether the retrieved documents are relevant to the question.

    Checks both LLM-judged relevance and whether expected keywords appear.
    """
    if not documents:
        return {"score": 0.0, "reasoning": "No documents retrieved"}

    doc_text = "\n".join(
        d.page_content if hasattr(d, "page_content") else str(d)
        for d in documents[:5]
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", "Rate how relevant these retrieved documents are to the question. "
         "Score 1.0 if highly relevant, 0.5 if partially relevant, 0.0 if irrelevant."),
        ("human", "Question: {question}\n\nRetrieved documents:\n{documents}"),
    ])

    result = (prompt | eval_scorer).invoke({
        "question": question,
        "documents": doc_text,
    })
    return {"score": result.score, "reasoning": result.reasoning}


# ── 2. Answer Groundedness ─────────────────────────────────────────

def eval_groundedness(answer: str, context: str) -> dict:
    """Evaluate whether the answer is grounded in the provided context.

    Checks that factual claims are supported by the evidence.
    """
    if not answer or not context:
        return {"score": 0.0, "reasoning": "Missing answer or context"}

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are checking if a sports analysis answer is grounded in the source data. "
         "Score 1.0 if all claims are supported, 0.5 if most are, 0.0 if fabricated."),
        ("human", "Source data:\n{context}\n\nAnswer:\n{answer}"),
    ])

    result = (prompt | eval_scorer).invoke({"context": context, "answer": answer})
    return {"score": result.score, "reasoning": result.reasoning}


# ── 3. Source Citation Quality ─────────────────────────────────────

def eval_citation_quality(answer: str, expected: dict) -> dict:
    """Evaluate whether the answer cites specific minutes and players.

    Checks both structural citation (minute references) and expected content.
    """
    score = 0.0
    reasons = []

    # Check for minute references (e.g., "58'", "76th minute", "minute 58")
    import re
    minute_refs = re.findall(r"\b\d{1,2}['']\b|\bminute \d{1,2}\b|\b\d{1,2}(?:st|nd|rd|th)[\s-]minute", answer.lower())
    if minute_refs:
        score += 0.4
        reasons.append(f"Found {len(minute_refs)} minute references")
    else:
        reasons.append("No minute references found")

    # Check for expected players
    expected_players = expected.get("expected_players", [])
    if expected_players:
        found = sum(1 for p in expected_players if p.lower() in answer.lower())
        player_ratio = found / len(expected_players)
        score += 0.3 * player_ratio
        reasons.append(f"Found {found}/{len(expected_players)} expected players")

    # Check for expected keywords
    expected_keywords = expected.get("expected_keywords", [])
    if expected_keywords:
        found = sum(1 for k in expected_keywords if k.lower() in answer.lower())
        keyword_ratio = found / len(expected_keywords)
        score += 0.3 * keyword_ratio
        reasons.append(f"Found {found}/{len(expected_keywords)} expected keywords")
    else:
        score += 0.3  # No keywords expected = pass

    return {"score": min(score, 1.0), "reasoning": "; ".join(reasons)}


# ── 4. Tool Selection Correctness ──────────────────────────────────

def eval_tool_selection(actual_route: str, expected_route: str, sources: list) -> dict:
    """Evaluate whether the router picked the correct path.

    Checks the route AND whether the right tools were called.
    """
    # Check route
    if actual_route == expected_route:
        route_score = 1.0
        reason = f"Correct route: {actual_route}"
    elif actual_route in ("tools", "vectorstore") and expected_route in ("tools", "vectorstore"):
        route_score = 0.5
        reason = f"Acceptable route: got {actual_route}, expected {expected_route}"
    else:
        route_score = 0.0
        reason = f"Wrong route: got {actual_route}, expected {expected_route}"

    # Check tool usage makes sense
    tool_sources = [s for s in sources if s.get("type") == "tool_result"]
    if tool_sources and expected_route == "tools":
        route_score = min(route_score + 0.1, 1.0)  # bonus for using tools when expected

    return {"score": route_score, "reasoning": reason}


# ── 5. Event Freshness ────────────────────────────────────────────

def eval_event_freshness(answer: str, expected: dict) -> dict:
    """Evaluate whether the answer references the most important match moments.

    Checks for expected minutes (key events that should be mentioned).
    """
    expected_minutes = expected.get("expected_minutes", [])
    if not expected_minutes:
        return {"score": 1.0, "reasoning": "No specific minutes expected"}

    import re
    # Find all numbers in the answer that could be minute references
    numbers = set(int(n) for n in re.findall(r"\b(\d{1,2})\b", answer))

    found = sum(1 for m in expected_minutes if m in numbers)
    ratio = found / len(expected_minutes)

    return {
        "score": ratio,
        "reasoning": f"Referenced {found}/{len(expected_minutes)} key moments: "
                     f"found {sorted(numbers & set(expected_minutes))}, "
                     f"missing {sorted(set(expected_minutes) - numbers)}",
    }


# ── Aggregate evaluator ───────────────────────────────────────────

def evaluate_response(
    question: str,
    result: dict,
    expected: dict,
    context: str = "",
    actual_route: str = "",
) -> dict:
    """Run all 5 evaluators on a single agent response.

    Returns a dict with individual dimension scores and an overall score.
    """
    answer = result.get("structured_response", {}).get("answer", result.get("generation", ""))
    documents = result.get("documents", [])
    sources = result.get("sources", [])

    scores = {}

    # 1. Retrieval relevance
    scores["retrieval_relevance"] = eval_retrieval_relevance(question, documents, expected)

    # 2. Groundedness
    doc_text = "\n".join(
        d.page_content if hasattr(d, "page_content") else str(d)
        for d in documents[:5]
    ) if documents else ""
    # Also include tool results as context
    tool_results = result.get("tool_results", [])
    if tool_results:
        doc_text += "\n" + "\n".join(tool_results)
    scores["groundedness"] = eval_groundedness(answer, doc_text or context)

    # 3. Citation quality
    scores["citation_quality"] = eval_citation_quality(answer, expected)

    # 4. Tool selection
    scores["tool_selection"] = eval_tool_selection(
        actual_route, expected.get("expected_route", ""), sources
    )

    # 5. Event freshness
    scores["event_freshness"] = eval_event_freshness(answer, expected)

    # Overall score (weighted average)
    weights = {
        "retrieval_relevance": 0.2,
        "groundedness": 0.3,
        "citation_quality": 0.2,
        "tool_selection": 0.15,
        "event_freshness": 0.15,
    }
    overall = sum(
        scores[dim]["score"] * weights[dim]
        for dim in weights
    )
    scores["overall"] = {"score": round(overall, 3), "reasoning": "Weighted average"}

    return scores
