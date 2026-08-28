# 04 — Storage Layer (`storage/`)

Two storage backends serve different query patterns. The agent uses both.

## `event_store.py` — SQLite for Structured Queries

`EventStore` wraps a SQLite database with three tables:

### Tables

| Table | Purpose |
|-------|---------|
| `matches` | One row per match: teams, competition, venue, formations, full metadata JSON |
| `events` | One row per event: flattened from `MatchEvent` with coordinates split into `x`/`y` columns |
| `lineups` | One row per player per team per match |

Three indexes speed up the most common queries: `(match_id, minute)`, `(match_id, player_name)`, `(match_id, event_type)`.

### Insert Methods

- `insert_match(metadata)` — writes to `matches` + `lineups` tables
- `insert_event(event)` — writes to `events` table. `additional_info` is stored as a JSON string.
- `ingest_match(feed)` — convenience that calls both

### Query Methods

These are what the agent's tools call:

| Method | What It Does |
|--------|-------------|
| `get_all_events(match_id)` | All events, ordered by minute |
| `get_events_by_time_range(match_id, start, end)` | Events within a minute window |
| `get_events_by_player(match_id, name)` | All events for a specific player |
| `get_events_by_type(match_id, type)` | All events of a given type |
| `get_match_summary(match_id)` | Computed summary: score (counted from goals), lineups, cards, subs |
| `get_player_stats(match_id, name)` | Aggregated: goals, assists, shots, xG, cards, fouls, key moments |
| `get_match_ids()` | List of all loaded matches |

All queries use parameterized statements (`?` placeholders) to prevent SQL injection.

The `_row_to_event()` helper reconstructs a full `MatchEvent` from a database row, including re-parsing `Coordinates` and `additional_info` from their stored forms.

### In-memory vs persistent

- Tests use `EventStore(":memory:")` for speed and isolation
- Production/demo uses `EventStore("./data/sports.db")` for persistence

## `vector_store.py` — Chroma for Semantic Search

`SportVectorStore` wraps LangChain's `Chroma` integration with sports-specific indexing.

### How events become documents

When you call `index_event()`, the event is converted to a LangChain `Document` with:

**`page_content`** (what gets embedded):
```
[ARS vs MCI] [Minute 76'] [Score: ARS 1 - 1 MCI] [Bukayo Saka (Arsenal)] [Goal]
GOAL! Arsenal equalise! Odegaard plays a sublime reverse pass to Saka...
```

The structured prefix tags (`[ARS vs MCI]`, `[Minute 76']`, etc.) help the embedding model understand context beyond just the narrative text.

**`metadata`** (for filtering):
```python
{
    "match_id": "match_001",
    "event_id": "evt_024",
    "minute": 76,
    "event_type": "goal",
    "player_name": "Bukayo Saka",
    "team": "Arsenal",
    "competition": "Premier League",
    "xg": 0.54
}
```

### Score tracking

`index_match()` tracks a running score dict as it processes events chronologically. Each document's `page_content` includes the score at the moment that event happened. So a search for "equaliser" will find documents that show `[Score: ARS 1 - 1 MCI]`.

### Searching

`search(query, match_id, filters, k)` runs a similarity search with optional metadata filters. You can filter by `match_id`, `event_type`, `player_name`, etc. Filters are combined with `$and` when multiple are provided.
