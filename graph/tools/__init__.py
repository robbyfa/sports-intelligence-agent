"""LangGraph structured tools for sports intelligence queries.

Tools access the stores via a module-level registry. Call ``configure()``
at startup to inject the ``EventStore`` and ``SportVectorStore`` instances
before the agent uses any tools.

Usage::

    from graph.tools import configure, get_all_tools

    configure(event_store=store, vector_store=vs)
    tools = get_all_tools()
"""

from graph.tools.registry import configure, get_event_store, get_vector_store
from graph.tools.timeline_tool import get_match_timeline
from graph.tools.player_stats_tool import get_player_stats
from graph.tools.match_summary_tool import get_match_summary
from graph.tools.event_search_tool import search_match_events


def get_all_tools() -> list:
    """Return all available tools for binding to the LLM."""
    return [
        get_match_timeline,
        get_player_stats,
        get_match_summary,
        search_match_events,
    ]


__all__ = [
    "configure",
    "get_all_tools",
    "get_event_store",
    "get_vector_store",
    "get_match_timeline",
    "get_player_stats",
    "get_match_summary",
    "search_match_events",
]
