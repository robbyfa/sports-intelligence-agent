"""SQLite-backed event store for structured sports event queries.

Stores match metadata, events, and lineups in normalised tables.
All queries use parameterized statements to prevent injection.

Usage::

    store = EventStore()  # in-memory for tests
    store = EventStore("./data/sports.db")  # persistent

    store.insert_match(metadata)
    store.insert_event(event)
    timeline = store.get_events_by_time_range("match_001", 60, 75)
"""

from __future__ import annotations

import json
import sqlite3
from typing import Optional

from models.events import (
    Coordinates,
    EventType,
    MatchEvent,
    MatchMetadata,
    MatchFeed,
)


class EventStore:
    """SQLite event store with structured query methods.

    Args:
        db_path: Path to the SQLite database file.
                 Use ``:memory:`` (default) for an in-memory database.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS matches (
                match_id      TEXT PRIMARY KEY,
                competition   TEXT,
                venue         TEXT,
                date          TEXT,
                home_team     TEXT,
                away_team     TEXT,
                home_formation TEXT,
                away_formation TEXT,
                metadata_json TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
                event_id            TEXT PRIMARY KEY,
                match_id            TEXT NOT NULL,
                minute              INTEGER NOT NULL,
                second              INTEGER NOT NULL DEFAULT 0,
                event_type          TEXT NOT NULL,
                player_name         TEXT,
                team                TEXT,
                x                   REAL,
                y                   REAL,
                xg                  REAL,
                narrative_text      TEXT,
                additional_info_json TEXT,
                FOREIGN KEY (match_id) REFERENCES matches(match_id)
            );

            CREATE TABLE IF NOT EXISTS lineups (
                match_id    TEXT NOT NULL,
                team        TEXT NOT NULL,
                player_name TEXT NOT NULL,
                number      INTEGER,
                position    TEXT,
                FOREIGN KEY (match_id) REFERENCES matches(match_id)
            );

            CREATE INDEX IF NOT EXISTS idx_events_match_minute
                ON events(match_id, minute);
            CREATE INDEX IF NOT EXISTS idx_events_match_player
                ON events(match_id, player_name);
            CREATE INDEX IF NOT EXISTS idx_events_match_type
                ON events(match_id, event_type);
            """
        )
        self._conn.commit()

    # ── Insert methods ─────────────────────────────────────────────

    def insert_match(self, metadata: MatchMetadata) -> None:
        """Insert match metadata and lineup rows."""
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO matches
                (match_id, competition, venue, date, home_team, away_team,
                 home_formation, away_formation, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata.match_id,
                metadata.competition,
                metadata.venue,
                metadata.date,
                metadata.home_team.name,
                metadata.away_team.name,
                metadata.home_formation,
                metadata.away_formation,
                metadata.model_dump_json(),
            ),
        )

        # Insert lineups for both teams
        for team_info in (metadata.home_team, metadata.away_team):
            for player in team_info.players:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO lineups
                        (match_id, team, player_name, number, position)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        metadata.match_id,
                        team_info.name,
                        player.name,
                        player.number,
                        player.position,
                    ),
                )
        self._conn.commit()

    def insert_event(self, event: MatchEvent) -> None:
        """Insert a single match event."""
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO events
                (event_id, match_id, minute, second, event_type,
                 player_name, team, x, y, xg,
                 narrative_text, additional_info_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.match_id,
                event.minute,
                event.second,
                event.event_type.value,
                event.player_name,
                event.team,
                event.coordinates.x if event.coordinates else None,
                event.coordinates.y if event.coordinates else None,
                event.xg,
                event.narrative_text,
                json.dumps(event.additional_info) if event.additional_info else None,
            ),
        )
        self._conn.commit()

    def ingest_match(self, feed: MatchFeed) -> None:
        """Convenience: insert match metadata and all events at once."""
        self.insert_match(feed.metadata)
        for event in feed.events:
            self.insert_event(event)

    # ── Query methods ──────────────────────────────────────────────

    def get_all_events(self, match_id: str) -> list[MatchEvent]:
        """Return all events for a match, ordered by minute."""
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT * FROM events
            WHERE match_id = ?
            ORDER BY minute, second
            """,
            (match_id,),
        )
        return [self._row_to_event(row) for row in cur.fetchall()]

    def get_events_by_time_range(
        self,
        match_id: str,
        start_minute: int,
        end_minute: int,
    ) -> list[MatchEvent]:
        """Return events within a minute range (inclusive)."""
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT * FROM events
            WHERE match_id = ? AND minute >= ? AND minute <= ?
            ORDER BY minute, second
            """,
            (match_id, start_minute, end_minute),
        )
        return [self._row_to_event(row) for row in cur.fetchall()]

    def get_events_by_player(
        self,
        match_id: str,
        player_name: str,
    ) -> list[MatchEvent]:
        """Return all events involving a specific player."""
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT * FROM events
            WHERE match_id = ? AND player_name = ?
            ORDER BY minute, second
            """,
            (match_id, player_name),
        )
        return [self._row_to_event(row) for row in cur.fetchall()]

    def get_events_by_type(
        self,
        match_id: str,
        event_type: str | EventType,
    ) -> list[MatchEvent]:
        """Return all events of a specific type."""
        if isinstance(event_type, EventType):
            event_type = event_type.value
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT * FROM events
            WHERE match_id = ? AND event_type = ?
            ORDER BY minute, second
            """,
            (match_id, event_type),
        )
        return [self._row_to_event(row) for row in cur.fetchall()]

    def get_match_summary(self, match_id: str) -> dict:
        """Build a match summary: score, teams, lineups, key moments.

        Returns a dict with keys: match_id, competition, venue, date,
        home_team, away_team, home_formation, away_formation,
        score (home, away), goals, cards, substitutions.
        """
        cur = self._conn.cursor()

        # Match metadata
        cur.execute("SELECT * FROM matches WHERE match_id = ?", (match_id,))
        match_row = cur.fetchone()
        if match_row is None:
            return {}

        # Compute score from goal events
        goals = self.get_events_by_type(match_id, EventType.GOAL)
        home_team = match_row["home_team"]
        away_team = match_row["away_team"]
        home_goals = [g for g in goals if g.team == home_team]
        away_goals = [g for g in goals if g.team == away_team]

        # Cards
        yellows = self.get_events_by_type(match_id, EventType.YELLOW_CARD)
        reds = self.get_events_by_type(match_id, EventType.RED_CARD)

        # Substitutions
        subs = self.get_events_by_type(match_id, EventType.SUBSTITUTION)

        # Lineups
        cur.execute(
            "SELECT player_name, number, position FROM lineups WHERE match_id = ? AND team = ?",
            (match_id, home_team),
        )
        home_lineup = [dict(row) for row in cur.fetchall()]

        cur.execute(
            "SELECT player_name, number, position FROM lineups WHERE match_id = ? AND team = ?",
            (match_id, away_team),
        )
        away_lineup = [dict(row) for row in cur.fetchall()]

        return {
            "match_id": match_id,
            "competition": match_row["competition"],
            "venue": match_row["venue"],
            "date": match_row["date"],
            "home_team": home_team,
            "away_team": away_team,
            "home_formation": match_row["home_formation"],
            "away_formation": match_row["away_formation"],
            "score": {
                "home": len(home_goals),
                "away": len(away_goals),
            },
            "goals": [
                {
                    "minute": g.minute,
                    "player": g.player_name,
                    "team": g.team,
                    "narrative": g.narrative_text,
                }
                for g in goals
            ],
            "cards": {
                "yellow": [
                    {"minute": c.minute, "player": c.player_name, "team": c.team}
                    for c in yellows
                ],
                "red": [
                    {"minute": c.minute, "player": c.player_name, "team": c.team}
                    for c in reds
                ],
            },
            "substitutions": [
                {
                    "minute": s.minute,
                    "team": s.team,
                    "out": s.additional_info.get("sub_out"),
                    "in": s.additional_info.get("sub_in"),
                }
                for s in subs
            ],
            "home_lineup": home_lineup,
            "away_lineup": away_lineup,
        }

    def get_player_stats(self, match_id: str, player_name: str) -> dict:
        """Aggregate a player's match statistics.

        Returns a dict with: player_name, team, goals, assists, shots,
        shots_on_target, xg_total, yellow_cards, red_cards, fouls_committed,
        pass_sequences_involved, key_events (list of narrative summaries).
        """
        events = self.get_events_by_player(match_id, player_name)
        if not events:
            return {"player_name": player_name, "events_found": 0}

        team = next((e.team for e in events if e.team), None)

        goals = [e for e in events if e.event_type == EventType.GOAL]
        assists = [e for e in events if e.event_type == EventType.ASSIST]
        shots = [e for e in events if e.event_type == EventType.SHOT]
        shots_on_target = [
            s for s in shots
            if s.additional_info.get("outcome") == "saved"
        ]
        yellows = [e for e in events if e.event_type == EventType.YELLOW_CARD]
        reds = [e for e in events if e.event_type == EventType.RED_CARD]
        fouls = [e for e in events if e.event_type == EventType.FOUL]
        pass_seqs = [e for e in events if e.event_type == EventType.PASS_SEQUENCE]
        penalties = [e for e in events if e.event_type == EventType.PENALTY]

        xg_total = sum(e.xg for e in events if e.xg is not None)

        key_events = [
            {"minute": e.minute, "type": e.event_type.value, "narrative": e.narrative_text}
            for e in events
            if e.event_type in (
                EventType.GOAL, EventType.ASSIST, EventType.RED_CARD,
                EventType.YELLOW_CARD, EventType.PENALTY,
            )
        ]

        return {
            "player_name": player_name,
            "team": team,
            "goals": len(goals),
            "assists": len(assists),
            "shots": len(shots),
            "shots_on_target": len(shots_on_target),
            "penalties": len(penalties),
            "xg_total": round(xg_total, 2),
            "yellow_cards": len(yellows),
            "red_cards": len(reds),
            "fouls_committed": len(fouls),
            "pass_sequences_involved": len(pass_seqs),
            "key_events": key_events,
        }

    def get_match_ids(self) -> list[str]:
        """Return all match IDs in the store."""
        cur = self._conn.cursor()
        cur.execute("SELECT match_id FROM matches ORDER BY date")
        return [row["match_id"] for row in cur.fetchall()]

    # ── Internal helpers ───────────────────────────────────────────

    def _row_to_event(self, row: sqlite3.Row) -> MatchEvent:
        """Convert a database row back to a MatchEvent."""
        coords = None
        if row["x"] is not None and row["y"] is not None:
            coords = Coordinates(x=row["x"], y=row["y"])

        additional_info = {}
        if row["additional_info_json"]:
            additional_info = json.loads(row["additional_info_json"])

        return MatchEvent(
            event_id=row["event_id"],
            match_id=row["match_id"],
            minute=row["minute"],
            second=row["second"],
            event_type=EventType(row["event_type"]),
            player_name=row["player_name"],
            team=row["team"],
            coordinates=coords,
            xg=row["xg"],
            narrative_text=row["narrative_text"],
            additional_info=additional_info,
        )

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
