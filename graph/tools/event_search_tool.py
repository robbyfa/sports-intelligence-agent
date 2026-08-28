"""Event search tool — semantic search over match events via Chroma."""

from langchain_core.tools import tool

from graph.tools.registry import get_vector_store


@tool
def search_match_events(query: str, match_id: str) -> str:
    """Search match events using natural language to find relevant moments.

    Use this tool when the user asks a broad or narrative question about the
    match that doesn't fit neatly into a timeline, player stats, or summary
    query. Good for questions like "What happened after the red card?",
    "Describe the build-up to the equaliser", "Were there any controversial
    moments?", or "What was the turning point?".

    Args:
        query: A natural-language description of what you're looking for.
        match_id: The match identifier (e.g. "match_001").

    Returns:
        Relevant match events with context, ordered by relevance.
    """
    store = get_vector_store()
    docs = store.search(query, match_id=match_id, k=5)

    if not docs:
        return f"No relevant events found for query: '{query}'"

    lines = [f"Search results for: '{query}' ({len(docs)} events found)"]
    lines.append("-" * 60)

    for i, doc in enumerate(docs, 1):
        meta = doc.metadata
        minute = meta.get("minute", "?")
        etype = meta.get("event_type", "unknown").replace("_", " ").title()
        player = meta.get("player_name", "")
        team = meta.get("team", "")
        event_id = meta.get("event_id", "")

        header = f"  [{i}] {minute}' - {etype}"
        if player:
            header += f" - {player}"
        if team:
            header += f" ({team})"

        lines.append(header)
        lines.append(f"       {doc.page_content}")
        lines.append(f"       [Source: {event_id}]")
        lines.append("")

    return "\n".join(lines)
