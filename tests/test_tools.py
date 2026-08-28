"""Tests for the LangGraph structured tools.

Each tool is tested independently with fixture data pre-loaded into both stores.
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

from fixtures import load_fixture
from models.events import MatchFeed
from storage.event_store import EventStore
from storage.vector_store import SportVectorStore
from streaming.pipeline import IngestionPipeline
from graph.tools import configure
from graph.tools.timeline_tool import get_match_timeline
from graph.tools.player_stats_tool import get_player_stats
from graph.tools.match_summary_tool import get_match_summary
from graph.tools.event_search_tool import search_match_events

needs_openai = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)


@pytest.fixture(scope="module")
def feed() -> MatchFeed:
    return load_fixture("match_001")


@pytest.fixture(scope="module")
def stores(feed):
    """Set up both stores and ingest the fixture match once for all tests."""
    es = EventStore(":memory:")
    vs = SportVectorStore(collection_name="test-tools")
    pipeline = IngestionPipeline(es, vs)
    pipeline.ingest_match(feed)
    configure(event_store=es, vector_store=vs)
    yield es, vs
    vs.reset()
    es.close()


# ── Timeline tool ──────────────────────────────────────────────────

@needs_openai
def test_timeline_returns_events_in_range(stores):
    result = get_match_timeline.invoke(
        {"match_id": "match_001", "start_minute": 60, "end_minute": 75}
    )
    assert "Timeline:" in result
    assert "60" in result or "62" in result or "63" in result
    # Should include the tactical shift, substitutions in this range
    assert "Substitution" in result or "Tactical Shift" in result


@needs_openai
def test_timeline_empty_range(stores):
    result = get_match_timeline.invoke(
        {"match_id": "match_001", "start_minute": 94, "end_minute": 100}
    )
    assert "No events found" in result


@needs_openai
def test_timeline_full_match(stores):
    result = get_match_timeline.invoke(
        {"match_id": "match_001", "start_minute": 0, "end_minute": 93}
    )
    assert "Kick Off" in result
    assert "Full Time" in result


# ── Player stats tool ─────────────────────────────────────────────

@needs_openai
def test_player_stats_saka(stores):
    result = get_player_stats.invoke(
        {"match_id": "match_001", "player_name": "Bukayo Saka"}
    )
    assert "Bukayo Saka" in result
    assert "Goals:" in result
    assert "Key moments:" in result


@needs_openai
def test_player_stats_de_bruyne(stores):
    result = get_player_stats.invoke(
        {"match_id": "match_001", "player_name": "Kevin De Bruyne"}
    )
    assert "Kevin De Bruyne" in result
    assert "Assists:" in result


@needs_openai
def test_player_stats_nonexistent(stores):
    result = get_player_stats.invoke(
        {"match_id": "match_001", "player_name": "Unknown Player"}
    )
    assert "No events found" in result


# ── Match summary tool ─────────────────────────────────────────────

@needs_openai
def test_match_summary_has_score(stores):
    result = get_match_summary.invoke({"match_id": "match_001"})
    assert "SCORE:" in result
    assert "Arsenal" in result
    assert "Manchester City" in result


@needs_openai
def test_match_summary_has_goals(stores):
    result = get_match_summary.invoke({"match_id": "match_001"})
    assert "Goals:" in result
    assert "Haaland" in result or "Saka" in result


@needs_openai
def test_match_summary_has_cards(stores):
    result = get_match_summary.invoke({"match_id": "match_001"})
    assert "Disciplinary:" in result
    assert "RED" in result  # Rodri red card


@needs_openai
def test_match_summary_has_lineups(stores):
    result = get_match_summary.invoke({"match_id": "match_001"})
    assert "Starting XI" in result
    assert "David Raya" in result  # Arsenal GK


@needs_openai
def test_match_summary_nonexistent(stores):
    result = get_match_summary.invoke({"match_id": "nonexistent"})
    assert "No match found" in result


# ── Event search tool ──────────────────────────────────────────────

@needs_openai
def test_event_search_red_card(stores):
    result = search_match_events.invoke(
        {"query": "red card sending off", "match_id": "match_001"}
    )
    assert "Search results" in result
    assert "Source:" in result
    # Should find the Rodri red card
    text_lower = result.lower()
    assert "red" in text_lower or "rodri" in text_lower


@needs_openai
def test_event_search_comeback(stores):
    result = search_match_events.invoke(
        {"query": "comeback equaliser turning point", "match_id": "match_001"}
    )
    assert len(result) > 0
    assert "Search results" in result


@needs_openai
def test_event_search_penalty(stores):
    result = search_match_events.invoke(
        {"query": "penalty VAR decision", "match_id": "match_001"}
    )
    assert "Search results" in result
    text_lower = result.lower()
    assert "penalty" in text_lower or "var" in text_lower
