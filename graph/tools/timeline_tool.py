"""Timeline tool — query events within a minute range."""

from langchain_core.tools import tool

from graph.tools.registry import get_event_store


@tool
def get_match_timeline(match_id: str, start_minute: int, end_minute: int) -> str:
    """Get all match events within a specific minute range.

    Use this tool when the user asks about what happened during a specific
    period of the match, e.g. "What happened between minute 60 and 75?"
    or "Show me the events in the second half" or "What changed after the
    red card?".

    Args:
        match_id: The match identifier (e.g. "match_001").
        start_minute: Start of the time range (inclusive).
        end_minute: End of the time range (inclusive).

    Returns:
        A formatted timeline of events with minute, type, player, and narrative.
    """
    store = get_event_store()
    events = store.get_events_by_time_range(match_id, start_minute, end_minute)

    if not events:
        return f"No events found between minute {start_minute} and {end_minute}."

    lines = [f"Timeline: Minute {start_minute}' to {end_minute}' ({len(events)} events)"]
    lines.append("-" * 60)

    for e in events:
        prefix = f"  {e.minute}'"
        etype = e.event_type.value.replace("_", " ").title()
        player = f" - {e.player_name}" if e.player_name else ""
        team = f" ({e.team})" if e.team else ""
        lines.append(f"{prefix} [{etype}]{player}{team}")
        lines.append(f"       {e.narrative_text}")

    return "\n".join(lines)
