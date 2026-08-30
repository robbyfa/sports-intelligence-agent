"""Analyst brief node — orchestrates the multi-step analyst brief workflow."""

from __future__ import annotations

from typing import Any, Dict

from graph.state import GraphState
from graph.workflows.analyst_brief import run_analyst_brief


def analyst_brief(state: GraphState) -> Dict[str, Any]:
    """Run the full analyst brief workflow.

    This is the "agentic" node: it autonomously gathers context from
    multiple sources, generates a structured brief, and verifies claims
    against the source data before returning.
    """
    print("---ANALYST BRIEF---")
    question = state["question"]
    match_id = state.get("match_id", "match_001")

    result = run_analyst_brief(question, match_id)

    return {
        "question": question,
        "generation": result["generation"],
        "structured_response": result["structured_response"],
        "sources": result["sources"],
        "documents": [],  # Brief workflow handles its own retrieval
        "retries": 99,    # Skip quality loop — brief has its own verification
    }
