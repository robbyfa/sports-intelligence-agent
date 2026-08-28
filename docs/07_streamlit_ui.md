# 07 — Streamlit UI (`app.py`)

The Streamlit app is the user-facing demo. It ties the entire pipeline together.

## Layout

### Sidebar

- **Match selection** — dropdown populated from `fixtures/` directory
- **Ingestion mode** — toggle between Batch (instant) and Real-time (events stream in with delays)
- **Speed multiplier** — slider for real-time mode (10x to 1000x)
- **Start Match** button — triggers ingestion
- **Status indicator** — shows "not started", "in progress", or "complete"
- **Match info** — teams, competition, venue, formations
- **Sample questions** — clickable examples for the chat

### Main Area (two tabs)

**Live Events tab:**
- Score header showing current state (e.g. "Arsenal 2 - 1 Manchester City")
- Scrollable event feed with coloured badges for each event type (green for goals, red for red cards, etc.)
- Events shown newest-first so the latest action is always visible

**Ask the Analyst tab:**
- Chat interface using Streamlit's `st.chat_message` / `st.chat_input`
- Agent responses display with a spinner during processing
- Evidence sources shown in expandable sections below each response

## How Ingestion Works

### Batch mode

Runs entirely in the main Streamlit thread:
1. Creates stores (SQLite in-memory, Chroma in-memory)
2. Creates an `IngestionPipeline`
3. Calls `pipeline.ingest_match(feed)` which produces/consumes/stores all events at once
4. Configures the agent tools and builds the graph
5. Reruns the page to show the results

### Real-time mode

This is trickier because Streamlit reruns the entire script on every interaction, and `st.session_state` is not accessible from background threads.

The solution:
1. `start_realtime()` runs in the main thread — creates stores, sets up session state, configures the agent
2. It then launches `_realtime_worker()` in a daemon thread, passing **plain Python objects** as arguments (stores, a shared list, a status dict)
3. The worker thread appends events to the shared list and writes to both stores. It never touches `st.session_state`.
4. The main thread auto-refreshes every 0.5 seconds during ingestion, re-reading the shared list to update the UI
5. When the worker finishes, it sets `status_box["done"] = True`. The main thread detects this on the next rerun and updates the status.

## Session State

All persistent state lives in `st.session_state`:

| Key | Type | Purpose |
|-----|------|---------|
| `event_store` | `EventStore` | SQLite store instance |
| `vector_store` | `SportVectorStore` | Chroma store instance |
| `agent` | compiled graph | The LangGraph agent |
| `match_loaded` | `bool` | Whether a match has been ingested |
| `match_status` | `str` | "not_started", "in_progress", or "complete" |
| `events_feed` | `list[MatchEvent]` | All ingested events (shared with worker thread) |
| `chat_history` | `list[dict]` | Messages for the chat UI |
| `active_match_id` | `str` | Current match ID |
| `active_feed` | `MatchFeed` | Current match feed object |

## Agent Invocation

When the user types a question in the chat:

```python
result = agent.invoke({
    "question": question,
    "match_id": match_id,
    "retries": 0,
})
```

The response includes `generation` (the answer text) and `sources` (evidence metadata). Sources are displayed in an expandable section showing which tools were called or which events were retrieved.
