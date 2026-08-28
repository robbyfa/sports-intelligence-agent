"""Event search node — semantic search over Chroma for match events."""

from __future__ import annotations

from typing import Any, Dict

from graph.state import GraphState
from graph.tools.registry import get_vector_store


def event_search(state: GraphState) -> Dict[str, Any]:
    """Perform semantic search over the sports event vector store.

    Returns matching documents with metadata for grading and generation.
    """
    print("---EVENT SEARCH---")
    question = state["question"]
    match_id = state.get("match_id", "match_001")

    store = get_vector_store()
    documents = store.search(question, match_id=match_id, k=5)

    # Extract source references from document metadata
    sources = []
    for doc in documents:
        meta = doc.metadata
        sources.append({
            "event_id": meta.get("event_id"),
            "minute": meta.get("minute"),
            "event_type": meta.get("event_type"),
            "player_name": meta.get("player_name"),
            "type": "vector_search",
        })

    print(f"  Found {len(documents)} relevant events")
    return {
        "documents": documents,
        "sources": sources,
        "question": question,
    }
