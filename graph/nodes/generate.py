"""Generate node — produces the structured sports analysis answer."""

from __future__ import annotations

from typing import Any, Dict

from graph.chains.generation import structured_generation_chain
from graph.state import GraphState
from models.analysis import StructuredAnalysis


def generate(state: GraphState) -> Dict[str, Any]:
    """Generate an evidence-grounded sports analysis answer.

    Uses the structured generation chain to produce a ``StructuredAnalysis``
    object with answer, evidence items, confidence, and sources.
    Falls back to a plain-text answer if structured output fails.

    The ``generation`` field in state is always a plain string (for grader
    compatibility). The full structured object is stored in ``structured_response``.
    """
    print("---GENERATE---")
    question = state["question"]
    documents = state["documents"]
    tool_results = state.get("tool_results", [])
    retries = state.get("retries", 0)

    # Build context from documents and tool results
    context_parts = []

    if tool_results:
        context_parts.append("=== Structured Tool Results ===")
        for result in tool_results:
            context_parts.append(result)

    if documents:
        context_parts.append("\n=== Retrieved Event Documents ===")
        for doc in documents:
            context_parts.append(doc.page_content)

    context = "\n\n".join(context_parts) if context_parts else "No context available."

    # Try structured output first
    try:
        analysis: StructuredAnalysis = structured_generation_chain.invoke(
            {"question": question, "context": context}
        )
        generation = analysis.format_plain()
        structured_response = analysis.model_dump()
    except Exception as e:
        print(f"  Structured generation failed ({e}), falling back to plain text")
        from graph.chains.generation import generation_chain

        generation = generation_chain.invoke(
            {"question": question, "context": context}
        )
        structured_response = {
            "answer": generation,
            "evidence": [],
            "confidence": "medium",
            "sources": ["unknown"],
        }

    return {
        "question": question,
        "documents": documents,
        "generation": generation,
        "structured_response": structured_response,
        "retries": retries + 1,
    }
