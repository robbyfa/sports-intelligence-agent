# 02 — Data Models (`models/events.py`)

This file defines the Pydantic models that represent everything about a match. Every other module in the project imports from here.

## Models

### `EventType` (enum)

A string enum with 16 event types:

```
goal, assist, substitution, yellow_card, red_card, shot, pass_sequence,
foul, corner, free_kick, penalty, var_decision, tactical_shift,
half_time, full_time, kick_off
```

Because it's a `str` enum, values serialize cleanly to JSON (`"goal"` not `"EventType.GOAL"`).

### `Player`

Simple: `name`, `number`, `position`. Used inside team lineups.

### `TeamInfo`

A team's `name`, `short_name` (e.g. "ARS"), and a `players` list.

### `Coordinates`

Pitch position with `x` and `y` both constrained to `0–100`. Optional on events — only shots and some fouls carry coordinates.

### `MatchMetadata`

Top-level match info: `match_id`, `competition`, `venue`, `date`, both `TeamInfo` objects, and both formations (e.g. "4-3-3").

### `MatchEvent`

The core model. Each event has:

| Field | Purpose |
|-------|---------|
| `event_id` | Unique ID like `"evt_024"` |
| `match_id` | Links to the match |
| `minute`, `second` | When it happened |
| `event_type` | One of the 16 `EventType` values |
| `player_name`, `team` | Who was involved (optional for half_time etc.) |
| `coordinates` | Where on the pitch (optional) |
| `xg` | Expected goals value for shots (optional, 0–1) |
| `preceding_events` | List of event IDs that led to this one |
| `narrative_text` | Human-readable description — this is what gets embedded in Chroma |
| `additional_info` | Flexible dict for event-specific extras (`sub_in`, `new_formation`, `var_outcome`, etc.) |

The `additional_info` dict is what keeps the schema sport-agnostic. Football substitutions store `sub_in`/`sub_out` there. An NFL event could store `yards_gained`/`down` in the same field.

### `MatchFeed`

Wraps `MatchMetadata` + a list of `MatchEvent`. Has two helper methods:
- `events_by_minute()` — returns events sorted chronologically
- `events_of_type(EventType)` — filters events by type

## Fixtures (`fixtures/`)

`match_001.json` is a complete Arsenal 2-1 Manchester City match with 36 events. The story: City dominate early, Haaland scores at 37', Rodri gets a red card at 58', Arsenal bring on Trossard, Saka equalises at 76', VAR awards a penalty at 88', Saka converts for 2-1.

The fixture covers all 16 event types. `fixtures/__init__.py` provides `load_fixture("match_001")` which returns a validated `MatchFeed`.
