"""Player stats tool — aggregate a player's match statistics."""

from langchain_core.tools import tool

from graph.tools.registry import get_event_store


@tool
def get_player_stats(match_id: str, player_name: str) -> str:
    """Get aggregated statistics for a specific player in a match.

    Use this tool when the user asks about a player's performance, impact,
    or contributions, e.g. "How did Saka play?", "What did De Bruyne do?",
    or "Which player had the biggest impact?".

    Args:
        match_id: The match identifier (e.g. "match_001").
        player_name: The player's full name (e.g. "Bukayo Saka").

    Returns:
        A formatted summary of the player's match statistics including goals,
        assists, shots, cards, and key events.
    """
    store = get_event_store()
    stats = store.get_player_stats(match_id, player_name)

    if stats.get("events_found") == 0:
        return f"No events found for player '{player_name}' in match {match_id}."

    lines = [f"Player Stats: {stats['player_name']} ({stats.get('team', 'N/A')})"]
    lines.append("-" * 50)
    lines.append(f"  Goals:          {stats['goals']}")
    lines.append(f"  Assists:        {stats['assists']}")
    lines.append(f"  Shots:          {stats['shots']}")
    lines.append(f"  Shots on target:{stats['shots_on_target']}")
    lines.append(f"  Penalties:      {stats['penalties']}")
    lines.append(f"  xG total:       {stats['xg_total']}")
    lines.append(f"  Yellow cards:   {stats['yellow_cards']}")
    lines.append(f"  Red cards:      {stats['red_cards']}")
    lines.append(f"  Fouls committed:{stats['fouls_committed']}")
    lines.append(f"  Pass sequences: {stats['pass_sequences_involved']}")

    if stats.get("key_events"):
        lines.append("")
        lines.append("Key moments:")
        for ke in stats["key_events"]:
            etype = ke["type"].replace("_", " ").title()
            lines.append(f"  {ke['minute']}' [{etype}] {ke['narrative']}")

    return "\n".join(lines)
