# 05 — Agent Tools (`graph/tools/`)

The agent has four tools it can call. Each is a LangChain `@tool`-decorated function that queries one of the storage backends and returns a formatted string.

## Dependency Injection via Registry

Tools need access to the `EventStore` and `SportVectorStore` instances, but `@tool` functions are plain functions — they can't take constructor arguments. The solution is `graph/tools/registry.py`:

```python
from graph.tools import configure

configure(event_store=store, vector_store=vs)
```

Call this once at startup. After that, each tool internally calls `get_event_store()` or `get_vector_store()` to get the shared instances.

## The Four Tools

### `get_match_timeline(match_id, start_minute, end_minute)`

**Source:** `timeline_tool.py` — queries `EventStore.get_events_by_time_range()`

**When the agent calls it:** Questions like "What happened between minute 60 and 75?" or "Show me the second half events."

**Returns:** A formatted list of events with minute, type, player, team, and narrative text.

### `get_player_stats(match_id, player_name)`

**Source:** `player_stats_tool.py` — queries `EventStore.get_player_stats()`

**When the agent calls it:** Questions like "How did Saka play?" or "What are Haaland's stats?"

**Returns:** Aggregated stats (goals, assists, shots, xG, cards, fouls) plus a list of key moments.

### `get_match_summary(match_id)`

**Source:** `match_summary_tool.py` — queries `EventStore.get_match_summary()`

**When the agent calls it:** Questions like "Summarise the match" or "What's the score?"

**Returns:** Full summary: score, goals, disciplinary record, substitutions, and starting lineups.

### `search_match_events(query, match_id)`

**Source:** `event_search_tool.py` — queries `SportVectorStore.search()`

**When the agent calls it:** Broad or narrative questions like "What was the turning point?" or "Were there any controversial moments?"

**Returns:** Top 5 semantically relevant events with metadata and source event IDs.

## How the LLM Picks Tools

The `tool_execute` node in the graph binds all four tools to the LLM using `llm.bind_tools(tools)`. The LLM reads each tool's docstring and decides which one(s) to call based on the user's question. The docstrings are carefully written with example questions to guide the LLM's routing.

## Adding a New Tool

1. Create `graph/tools/my_new_tool.py` with a `@tool`-decorated function
2. Add it to the `get_all_tools()` list in `graph/tools/__init__.py`
3. The LLM will discover it automatically from its docstring
