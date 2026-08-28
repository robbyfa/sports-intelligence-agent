"""Tests for the SQLite event store."""

import pytest

from fixtures import load_fixture
from models.events import EventType, MatchFeed
from storage.event_store import EventStore


@pytest.fixture
def feed() -> MatchFeed:
    return load_fixture("match_001")


@pytest.fixture
def store(feed) -> EventStore:
    """In-memory event store pre-loaded with the fixture match."""
    s = EventStore(":memory:")
    s.ingest_match(feed)
    yield s
    s.close()


# ── Insert / basic retrieval ───────────────────────────────────────

def test_get_all_events_count(store, feed):
    events = store.get_all_events("match_001")
    assert len(events) == len(feed.events)


def test_get_all_events_ordered_by_minute(store):
    events = store.get_all_events("match_001")
    for i in range(len(events) - 1):
        a, b = events[i], events[i + 1]
        assert (a.minute, a.second) <= (b.minute, b.second)


def test_get_match_ids(store):
    ids = store.get_match_ids()
    assert ids == ["match_001"]


# ── Time range queries ─────────────────────────────────────────────

def test_get_events_by_time_range_returns_correct_window(store):
    events = store.get_events_by_time_range("match_001", 60, 75)
    assert len(events) > 0
    for e in events:
        assert 60 <= e.minute <= 75


def test_get_events_by_time_range_first_half(store):
    events = store.get_events_by_time_range("match_001", 0, 45)
    for e in events:
        assert e.minute <= 45


def test_get_events_by_time_range_empty(store):
    events = store.get_events_by_time_range("match_001", 94, 100)
    assert events == []


# ── Player queries ─────────────────────────────────────────────────

def test_get_events_by_player_saka(store):
    events = store.get_events_by_player("match_001", "Bukayo Saka")
    assert len(events) >= 3  # shot, goal, penalty at minimum
    assert all(e.player_name == "Bukayo Saka" for e in events)


def test_get_events_by_player_haaland(store):
    events = store.get_events_by_player("match_001", "Erling Haaland")
    assert len(events) >= 2  # goal + shots
    goals = [e for e in events if e.event_type == EventType.GOAL]
    assert len(goals) >= 1


def test_get_events_by_player_nonexistent(store):
    events = store.get_events_by_player("match_001", "Unknown Player")
    assert events == []


# ── Event type queries ─────────────────────────────────────────────

def test_get_events_by_type_goal(store):
    goals = store.get_events_by_type("match_001", EventType.GOAL)
    assert len(goals) >= 2  # At least Haaland + Saka goals
    assert all(g.event_type == EventType.GOAL for g in goals)


def test_get_events_by_type_string(store):
    """Accepts string values as well as enum."""
    goals = store.get_events_by_type("match_001", "goal")
    assert len(goals) >= 2


def test_get_events_by_type_red_card(store):
    reds = store.get_events_by_type("match_001", EventType.RED_CARD)
    assert len(reds) == 1
    assert reds[0].player_name == "Rodri"


def test_get_events_by_type_substitution(store):
    subs = store.get_events_by_type("match_001", EventType.SUBSTITUTION)
    assert len(subs) >= 3


# ── Match summary ──────────────────────────────────────────────────

def test_get_match_summary_basic_fields(store):
    summary = store.get_match_summary("match_001")
    assert summary["match_id"] == "match_001"
    assert summary["home_team"] == "Arsenal"
    assert summary["away_team"] == "Manchester City"
    assert summary["competition"] == "Premier League"


def test_get_match_summary_score(store):
    summary = store.get_match_summary("match_001")
    assert summary["score"]["home"] == 2  # Saka x2
    assert summary["score"]["away"] == 1  # Haaland


def test_get_match_summary_goals_detail(store):
    summary = store.get_match_summary("match_001")
    goal_players = [g["player"] for g in summary["goals"]]
    assert "Erling Haaland" in goal_players
    assert "Bukayo Saka" in goal_players


def test_get_match_summary_cards(store):
    summary = store.get_match_summary("match_001")
    yellow_players = [c["player"] for c in summary["cards"]["yellow"]]
    red_players = [c["player"] for c in summary["cards"]["red"]]
    assert "Rodri" in red_players
    assert len(summary["cards"]["yellow"]) >= 2


def test_get_match_summary_substitutions(store):
    summary = store.get_match_summary("match_001")
    subs = summary["substitutions"]
    assert len(subs) >= 3
    sub_ins = [s["in"] for s in subs]
    assert "Manuel Akanji" in sub_ins
    assert "Leandro Trossard" in sub_ins


def test_get_match_summary_lineups(store):
    summary = store.get_match_summary("match_001")
    assert len(summary["home_lineup"]) == 11
    assert len(summary["away_lineup"]) == 11


def test_get_match_summary_nonexistent(store):
    summary = store.get_match_summary("nonexistent")
    assert summary == {}


# ── Player stats ───────────────────────────────────────────────────

def test_player_stats_saka(store):
    stats = store.get_player_stats("match_001", "Bukayo Saka")
    assert stats["player_name"] == "Bukayo Saka"
    assert stats["team"] == "Arsenal"
    assert stats["goals"] >= 2  # open play + penalty
    assert stats["penalties"] >= 1
    assert stats["xg_total"] > 0
    assert len(stats["key_events"]) >= 2


def test_player_stats_haaland(store):
    stats = store.get_player_stats("match_001", "Erling Haaland")
    assert stats["goals"] >= 1
    assert stats["shots"] >= 1
    assert stats["xg_total"] > 0


def test_player_stats_rodri(store):
    stats = store.get_player_stats("match_001", "Rodri")
    assert stats["red_cards"] == 1
    assert len(stats["key_events"]) >= 1


def test_player_stats_de_bruyne(store):
    stats = store.get_player_stats("match_001", "Kevin De Bruyne")
    assert stats["assists"] >= 1
    assert stats["pass_sequences_involved"] >= 1


def test_player_stats_nonexistent(store):
    stats = store.get_player_stats("match_001", "Nobody")
    assert stats["events_found"] == 0


# ── Round-trip fidelity ────────────────────────────────────────────

def test_event_round_trip_preserves_fields(store, feed):
    """Events survive insert → read without data loss."""
    original = feed.events[0]
    retrieved = store.get_all_events("match_001")
    first = next(e for e in retrieved if e.event_id == original.event_id)

    assert first.event_id == original.event_id
    assert first.minute == original.minute
    assert first.event_type == original.event_type
    assert first.narrative_text == original.narrative_text


def test_event_with_coordinates_round_trip(store):
    """Coordinates survive the round trip."""
    shots = store.get_events_by_type("match_001", EventType.SHOT)
    for shot in shots:
        assert shot.coordinates is not None
        assert 0 <= shot.coordinates.x <= 100
        assert 0 <= shot.coordinates.y <= 100


def test_event_additional_info_round_trip(store):
    """additional_info dict survives JSON serialization."""
    subs = store.get_events_by_type("match_001", EventType.SUBSTITUTION)
    for sub in subs:
        assert "sub_in" in sub.additional_info
        assert "sub_out" in sub.additional_info
