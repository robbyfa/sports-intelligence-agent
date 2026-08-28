"""Generate node — produces the sports analysis answer."""

from __future__ import annotations

from typing import Any, Dict

from graph.chains.generation import generation_chain
from graph.state import GraphState


def generate(state: GraphState) -> Dict[str, Any]:
    """Generate an evidence-grounded sports analysis answer.

    Combines documents and tool results as context for the generation chain.
    Increments the retry counter to prevent infinite loops.
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

    generation = generation_chain.invoke(
        {"question": question, "context": context}
    )

    return {
        "question": question,
        "documents": documents,
        "generation": generation,
        "retries": retries + 1,
    }
