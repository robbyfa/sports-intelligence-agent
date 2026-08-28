"""Tests for the sports event data models and fixture loading."""

import json
from pathlib import Path

import pytest

from models.events import (
    Coordinates,
    EventType,
    MatchEvent,
    MatchFeed,
    MatchMetadata,
    Player,
    TeamInfo,
)
from fixtures import load_fixture, list_fixtures


# ── Fixture loading ────────────────────────────────────────────────

def test_list_fixtures_finds_match_001():
    names = list_fixtures()
    assert "match_001" in names


def test_load_fixture_returns_match_feed():
    feed = load_fixture("match_001")
    assert isinstance(feed, MatchFeed)


def test_load_fixture_not_found():
    with pytest.raises(FileNotFoundError):
        load_fixture("nonexistent_match")


# ── MatchMetadata ──────────────────────────────────────────────────

def test_metadata_fields():
    feed = load_fixture("match_001")
    meta = feed.metadata
    assert meta.match_id == "match_001"
    assert meta.competition == "Premier League"
    assert meta.venue == "Emirates Stadium"
    assert meta.home_team.name == "Arsenal"
    assert meta.away_team.name == "Manchester City"
    assert meta.home_formation == "4-3-3"
    assert meta.away_formation == "4-2-3-1"


def test_lineup_has_11_players():
    feed = load_fixture("match_001")
    assert len(feed.metadata.home_team.players) == 11
    assert len(feed.metadata.away_team.players) == 11


def test_player_model():
    player = Player(name="Bukayo Saka", number=7, position="RW")
    assert player.name == "Bukayo Saka"
    assert player.number == 7
    assert player.position == "RW"


# ── Event types coverage ──────────────────────────────────────────

def test_all_event_types_present_in_fixture():
    feed = load_fixture("match_001")
    event_types_in_fixture = {e.event_type for e in feed.events}

    expected_types = {
        EventType.GOAL,
        EventType.ASSIST,
        EventType.SUBSTITUTION,
        EventType.YELLOW_CARD,
        EventType.RED_CARD,
        EventType.SHOT,
        EventType.PASS_SEQUENCE,
        EventType.FOUL,
        EventType.CORNER,
        EventType.FREE_KICK,
        EventType.PENALTY,
        EventType.VAR_DECISION,
        EventType.TACTICAL_SHIFT,
        EventType.HALF_TIME,
        EventType.FULL_TIME,
        EventType.KICK_OFF,
    }

    missing = expected_types - event_types_in_fixture
    assert not missing, f"Missing event types in fixture: {missing}"


# ── MatchEvent validation ─────────────────────────────────────────

def test_event_has_narrative_text():
    feed = load_fixture("match_001")
    for event in feed.events:
        assert event.narrative_text, f"Event {event.event_id} missing narrative_text"


def test_goal_event_has_xg():
    feed = load_fixture("match_001")
    goals = feed.events_of_type(EventType.GOAL)
    assert len(goals) >= 2, "Expected at least 2 goals in fixture"
    for goal in goals:
        assert goal.xg is not None, f"Goal {goal.event_id} missing xG"


def test_shot_event_has_coordinates():
    feed = load_fixture("match_001")
    shots = feed.events_of_type(EventType.SHOT)
    for shot in shots:
        assert shot.coordinates is not None, f"Shot {shot.event_id} missing coordinates"


def test_substitution_has_sub_info():
    feed = load_fixture("match_001")
    subs = feed.events_of_type(EventType.SUBSTITUTION)
    assert len(subs) >= 2
    for sub in subs:
        assert "sub_in" in sub.additional_info, f"Sub {sub.event_id} missing sub_in"
        assert "sub_out" in sub.additional_info, f"Sub {sub.event_id} missing sub_out"


# ── Coordinates validation ────────────────────────────────────────

def test_coordinates_valid_range():
    c = Coordinates(x=50.0, y=50.0)
    assert c.x == 50.0
    assert c.y == 50.0


def test_coordinates_rejects_out_of_range():
    with pytest.raises(Exception):
        Coordinates(x=150.0, y=50.0)
    with pytest.raises(Exception):
        Coordinates(x=50.0, y=-10.0)


# ── MatchFeed helpers ─────────────────────────────────────────────

def test_events_by_minute_sorted():
    feed = load_fixture("match_001")
    ordered = feed.events_by_minute()
    for i in range(len(ordered) - 1):
        a, b = ordered[i], ordered[i + 1]
        assert (a.minute, a.second) <= (b.minute, b.second), (
            f"Events out of order: {a.event_id}@{a.minute}' vs {b.event_id}@{b.minute}'"
        )


def test_events_of_type_filters_correctly():
    feed = load_fixture("match_001")
    goals = feed.events_of_type(EventType.GOAL)
    assert all(g.event_type == EventType.GOAL for g in goals)
    assert len(goals) >= 2


# ── Pydantic round-trip (JSON serialization) ──────────────────────

def test_match_feed_round_trip():
    feed = load_fixture("match_001")
    json_str = feed.model_dump_json()
    restored = MatchFeed.model_validate_json(json_str)
    assert len(restored.events) == len(feed.events)
    assert restored.metadata.match_id == feed.metadata.match_id


def test_event_count():
    feed = load_fixture("match_001")
    assert len(feed.events) >= 30, f"Expected 30+ events, got {len(feed.events)}"
