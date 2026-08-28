"""Match summary tool — get current score, lineups, and key moments."""

from langchain_core.tools import tool

from graph.tools.registry import get_event_store


@tool
def get_match_summary(match_id: str) -> str:
    """Get a comprehensive match summary including score, lineups, and key moments.

    Use this tool when the user asks for an overview of the match, the current
    score, who is playing, or wants a general summary, e.g. "Summarise the match",
    "What's the score?", "Give me a match report", or "What are the key talking
    points?".

    Args:
        match_id: The match identifier (e.g. "match_001").

    Returns:
        A formatted match summary with score, goals, cards, substitutions,
        and lineup information.
    """
    store = get_event_store()
    summary = store.get_match_summary(match_id)

    if not summary:
        return f"No match found with ID '{match_id}'."

    score = summary["score"]
    lines = [
        f"Match Summary: {summary['home_team']} vs {summary['away_team']}",
        f"Competition: {summary['competition']} | Venue: {summary['venue']} | Date: {summary['date']}",
        f"Formation: {summary['home_team']} ({summary['home_formation']}) vs "
        f"{summary['away_team']} ({summary['away_formation']})",
        "",
        f"SCORE: {summary['home_team']} {score['home']} - {score['away']} {summary['away_team']}",
        "",
    ]

    # Goals
    if summary["goals"]:
        lines.append("Goals:")
        for g in summary["goals"]:
            lines.append(f"  {g['minute']}' {g['player']} ({g['team']})")
        lines.append("")

    # Cards
    all_cards = summary["cards"]["yellow"] + summary["cards"]["red"]
    if all_cards:
        lines.append("Disciplinary:")
        for c in summary["cards"]["yellow"]:
            lines.append(f"  {c['minute']}' Yellow - {c['player']} ({c['team']})")
        for c in summary["cards"]["red"]:
            lines.append(f"  {c['minute']}' RED - {c['player']} ({c['team']})")
        lines.append("")

    # Substitutions
    if summary["substitutions"]:
        lines.append("Substitutions:")
        for s in summary["substitutions"]:
            lines.append(
                f"  {s['minute']}' {s['team']}: {s['out']} OFF, {s['in']} ON"
            )
        lines.append("")

    # Lineups
    lines.append(f"Starting XI - {summary['home_team']}:")
    for p in summary["home_lineup"]:
        lines.append(f"  #{p['number']} {p['player_name']} ({p['position']})")

    lines.append(f"\nStarting XI - {summary['away_team']}:")
    for p in summary["away_lineup"]:
        lines.append(f"  #{p['number']} {p['player_name']} ({p['position']})")

    return "\n".join(lines)
