"""Pydantic data models for sports events.

Sport-agnostic schema with football/soccer as the first implementation.
Designed to be extensible — add new EventType values and additional_info
fields for other sports (NFL, basketball, etc.) without breaking existing code.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of match events. Extensible for new sports."""

    GOAL = "goal"
    ASSIST = "assist"
    SUBSTITUTION = "substitution"
    YELLOW_CARD = "yellow_card"
    RED_CARD = "red_card"
    SHOT = "shot"
    PASS_SEQUENCE = "pass_sequence"
    FOUL = "foul"
    CORNER = "corner"
    FREE_KICK = "free_kick"
    PENALTY = "penalty"
    VAR_DECISION = "var_decision"
    TACTICAL_SHIFT = "tactical_shift"
    HALF_TIME = "half_time"
    FULL_TIME = "full_time"
    KICK_OFF = "kick_off"


class Player(BaseModel):
    """A player in a team lineup."""

    name: str
    number: int
    position: str  # e.g. "GK", "CB", "CM", "ST"


class TeamInfo(BaseModel):
    """Team metadata including lineup."""

    name: str
    short_name: str
    players: list[Player] = Field(default_factory=list)


class Coordinates(BaseModel):
    """Pitch coordinates for event location (0-100 range for both axes)."""

    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)


class MatchMetadata(BaseModel):
    """Top-level match information."""

    match_id: str
    competition: str
    venue: str
    date: str  # ISO date string e.g. "2024-11-23"
    home_team: TeamInfo
    away_team: TeamInfo
    home_formation: str = "4-3-3"  # e.g. "4-3-3", "4-4-2"
    away_formation: str = "4-2-3-1"


class MatchEvent(BaseModel):
    """A single event that occurs during a match.

    The ``narrative_text`` field is the human-readable description that gets
    embedded into the vector store for semantic retrieval.  ``additional_info``
    is a flexible dict for event-specific data (sub_in player, new formation,
    VAR outcome, etc.) so the schema stays sport-agnostic.
    """

    event_id: str
    match_id: str
    minute: int = Field(ge=0)
    second: int = Field(ge=0, le=59, default=0)
    event_type: EventType
    player_name: Optional[str] = None  # None for events like half_time
    team: Optional[str] = None
    coordinates: Optional[Coordinates] = None
    xg: Optional[float] = Field(default=None, ge=0, le=1)
    preceding_events: list[str] = Field(default_factory=list)
    narrative_text: str
    additional_info: dict = Field(default_factory=dict)


class MatchFeed(BaseModel):
    """Complete match data: metadata + ordered list of events."""

    metadata: MatchMetadata
    events: list[MatchEvent]

    def events_by_minute(self) -> list[MatchEvent]:
        """Return events sorted by (minute, second)."""
        return sorted(self.events, key=lambda e: (e.minute, e.second))

    def events_of_type(self, event_type: EventType) -> list[MatchEvent]:
        """Filter events by type."""
        return [e for e in self.events if e.event_type == event_type]
