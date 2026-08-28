"""Graph state for the sports intelligence agent."""

from __future__ import annotations

from typing import List, Optional, TypedDict


class GraphState(TypedDict):
    """Represents the state of the sports intelligence LangGraph agent.

    Attributes:
        question: The user's question.
        match_id: The active match identifier.
        generation: The LLM-generated answer.
        web_search: Whether to fall back to web search.
        documents: Retrieved context documents (from Chroma or tools).
        tool_results: Formatted results from structured tool calls.
        sources: Evidence attribution — list of dicts with event_id, minute, narrative.
        retries: Number of generation retries (to prevent infinite loops).
    """

    question: str
    match_id: str
    generation: str
    web_search: bool
    documents: List[str]
    tool_results: List[str]
    sources: List[dict]
    retries: int
