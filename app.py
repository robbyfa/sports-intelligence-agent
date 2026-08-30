"""Streamlit UI for the Streaming Sports Intelligence Agent.

Run with: streamlit run app.py
"""

from __future__ import annotations

import threading
import time

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from fixtures import load_fixture, list_fixtures
from graph.graph import build_graph
from graph.tools import configure
from models.events import EventType, MatchEvent, MatchFeed
from storage.event_store import EventStore
from storage.vector_store import SportVectorStore
from streaming.pipeline import IngestionPipeline

# ── Page config ────────────────────────────────────────────────────

st.set_page_config(
    page_title="Sports Intelligence Agent",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Event type styling ─────────────────────────────────────────────

EVENT_BADGES = {
    EventType.GOAL: ("GOAL", "#22c55e"),
    EventType.ASSIST: ("ASSIST", "#3b82f6"),
    EventType.SUBSTITUTION: ("SUB", "#f59e0b"),
    EventType.YELLOW_CARD: ("YELLOW", "#eab308"),
    EventType.RED_CARD: ("RED CARD", "#ef4444"),
    EventType.SHOT: ("SHOT", "#8b5cf6"),
    EventType.PASS_SEQUENCE: ("PASS SEQ", "#06b6d4"),
    EventType.FOUL: ("FOUL", "#f97316"),
    EventType.CORNER: ("CORNER", "#6366f1"),
    EventType.FREE_KICK: ("FREE KICK", "#10b981"),
    EventType.PENALTY: ("PENALTY", "#ef4444"),
    EventType.VAR_DECISION: ("VAR", "#ec4899"),
    EventType.TACTICAL_SHIFT: ("TACTICS", "#14b8a6"),
    EventType.HALF_TIME: ("HT", "#6b7280"),
    EventType.FULL_TIME: ("FT", "#6b7280"),
    EventType.KICK_OFF: ("KO", "#6b7280"),
}


def event_badge(event: MatchEvent) -> str:
    """Return an HTML badge for the event type."""
    label, color = EVENT_BADGES.get(event.event_type, ("EVENT", "#6b7280"))
    return (
        f'<span style="background-color:{color};color:white;padding:2px 8px;'
        f'border-radius:4px;font-size:0.75rem;font-weight:600;">{label}</span>'
    )


def render_event(event: MatchEvent) -> str:
    """Render a single event as styled HTML."""
    badge = event_badge(event)
    minute = f"<strong>{event.minute}'</strong>"
    player = f" — {event.player_name}" if event.player_name else ""
    team = f" ({event.team})" if event.team else ""

    return (
        f'<div style="padding:8px 0;border-bottom:1px solid #e5e7eb;">'
        f'{minute} {badge}{player}{team}'
        f'<br><span style="color:#4b5563;font-size:0.9rem;">{event.narrative_text}</span>'
        f'</div>'
    )


# ── Session state initialisation ──────────────────────────────────

def init_session_state():
    """Initialise all session state keys."""
    defaults = {
        "event_store": None,
        "vector_store": None,
        "agent": None,
        "match_loaded": False,
        "match_status": "not_started",
        "events_feed": [],       # plain list — shared with background thread
        "chat_history": [],
        "active_match_id": None,
        "active_feed": None,
        "ingestion_complete": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session_state()


# ── Store setup ────────────────────────────────────────────────────

def setup_stores():
    """Create or reuse the stores. Must be called from the main thread."""
    if st.session_state.event_store is None:
        st.session_state.event_store = EventStore(":memory:")
    if st.session_state.vector_store is None:
        st.session_state.vector_store = SportVectorStore(
            collection_name="sports-events-ui"
        )


def setup_agent():
    """Configure tools and build the graph. Must be called from the main thread."""
    configure(
        event_store=st.session_state.event_store,
        vector_store=st.session_state.vector_store,
    )
    if st.session_state.agent is None:
        st.session_state.agent = build_graph()


# ── Ingestion functions ────────────────────────────────────────────

def ingest_batch(feed: MatchFeed):
    """Ingest all events at once (runs in the main thread)."""
    setup_stores()
    pipeline = IngestionPipeline(
        st.session_state.event_store,
        st.session_state.vector_store,
    )

    events_list: list[MatchEvent] = []

    def on_event(event: MatchEvent):
        events_list.append(event)

    pipeline.ingest_match(feed, on_event=on_event)

    st.session_state.events_feed = events_list
    st.session_state.match_loaded = True
    st.session_state.match_status = "complete"
    st.session_state.active_match_id = feed.metadata.match_id
    st.session_state.active_feed = feed
    st.session_state.ingestion_complete = True

    setup_agent()


def _realtime_worker(
    feed: MatchFeed,
    speed: float,
    event_store: EventStore,
    vector_store: SportVectorStore,
    events_feed: list[MatchEvent],
    status_box: dict,
):
    """Background worker for real-time ingestion.

    Operates only on plain Python objects passed in as arguments —
    never touches ``st.session_state`` (which is thread-local to the
    Streamlit script thread).
    """
    pipeline = IngestionPipeline(event_store, vector_store)
    pipeline._metadata = feed.metadata

    events = feed.events_by_minute()
    prev_match_seconds = 0.0

    for event in events:
        current_match_seconds = event.minute * 60 + event.second
        gap = current_match_seconds - prev_match_seconds
        if gap > 0:
            time.sleep(gap / speed)
        prev_match_seconds = current_match_seconds

        pipeline.ingest_event(event, feed.metadata)
        events_feed.append(event)  # mutates the shared list

    status_box["done"] = True


def start_realtime(feed: MatchFeed, speed: float):
    """Prepare stores & session state in the main thread, then launch worker."""
    setup_stores()

    # Insert match metadata from the main thread
    st.session_state.event_store.insert_match(feed.metadata)

    st.session_state.match_loaded = True
    st.session_state.match_status = "in_progress"
    st.session_state.active_match_id = feed.metadata.match_id
    st.session_state.active_feed = feed
    st.session_state.ingestion_complete = False
    st.session_state.events_feed = []  # fresh list the worker will mutate

    setup_agent()

    # A mutable dict the thread writes to when it finishes
    status_box: dict = {"done": False}
    st.session_state["_rt_status_box"] = status_box

    thread = threading.Thread(
        target=_realtime_worker,
        args=(
            feed,
            speed,
            st.session_state.event_store,
            st.session_state.vector_store,
            st.session_state.events_feed,
            status_box,
        ),
        daemon=True,
    )
    thread.start()


# ── Sidebar ────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Sports Intelligence Agent")
    st.markdown("---")

    # Match selection
    fixtures = list_fixtures()
    fixture_labels = {f: f.replace("_", " ").title() for f in fixtures}
    selected = st.selectbox(
        "Select Match",
        fixtures,
        format_func=lambda x: fixture_labels[x],
    )

    # Mode
    mode = st.radio("Ingestion Mode", ["Batch", "Real-time"], horizontal=True)

    # Speed (real-time only)
    speed = 100.0
    if mode == "Real-time":
        speed = st.slider(
            "Speed Multiplier",
            min_value=10.0,
            max_value=1000.0,
            value=100.0,
            step=10.0,
            help="How much faster than real-time. 100x = 93 min match in ~56 seconds.",
        )

    # Start button
    start_disabled = st.session_state.match_status == "in_progress"
    if st.button(
        "Start Match",
        disabled=start_disabled,
        use_container_width=True,
        type="primary",
    ):
        # Reset state for a new match
        st.session_state.events_feed = []
        st.session_state.chat_history = []
        st.session_state.match_loaded = False
        st.session_state.match_status = "not_started"
        st.session_state.ingestion_complete = False
        st.session_state.agent = None

        # Reset stores
        if st.session_state.event_store:
            st.session_state.event_store.close()
        st.session_state.event_store = None
        st.session_state.vector_store = None

        feed = load_fixture(selected)

        if mode == "Batch":
            with st.spinner(f"Ingesting {len(feed.events)} events..."):
                ingest_batch(feed)
            st.rerun()
        else:
            start_realtime(feed, speed)
            st.rerun()

    # Status indicator
    st.markdown("---")
    status = st.session_state.match_status

    # Check if the background worker has finished
    if status == "in_progress":
        status_box = st.session_state.get("_rt_status_box", {})
        if status_box.get("done"):
            st.session_state.match_status = "complete"
            st.session_state.ingestion_complete = True
            status = "complete"

    if status == "not_started":
        st.info("No match loaded")
    elif status == "in_progress":
        event_count = len(st.session_state.events_feed)
        st.warning(f"Match in progress... ({event_count} events)")
        if st.button("Refresh", use_container_width=True):
            st.rerun()
    elif status == "complete":
        event_count = len(st.session_state.events_feed)
        st.success(f"Match complete ({event_count} events)")

    # Match info
    if st.session_state.active_feed:
        meta = st.session_state.active_feed.metadata
        st.markdown("---")
        st.markdown(f"**{meta.home_team.name}** vs **{meta.away_team.name}**")
        st.markdown(f"{meta.competition} | {meta.venue}")
        st.markdown(f"{meta.date}")
        st.markdown(f"Formation: {meta.home_formation} vs {meta.away_formation}")

    # Sample questions
    st.markdown("---")
    st.markdown("**Try asking:**")
    sample_questions = [
        "Summarise the match",
        "What changed after the red card?",
        "Which player had the biggest impact?",
        "What happened between minute 60 and 80?",
        "What are the key talking points?",
        "How did Saka play?",
    ]
    for q in sample_questions:
        st.markdown(f"- {q}")


# ── Main content ───────────────────────────────────────────────────

# Auto-refresh during real-time ingestion
if st.session_state.match_status == "in_progress":
    time.sleep(0.5)
    st.rerun()

events_tab, analyst_tab = st.tabs(["Live Events", "Ask the Analyst"])

# ── Live Events tab ────────────────────────────────────────────────

with events_tab:
    if not st.session_state.events_feed:
        st.markdown(
            '<div style="text-align:center;padding:60px;color:#9ca3af;">'
            '<p style="font-size:1.2rem;">No events yet.</p>'
            '<p>Select a match and click <strong>Start Match</strong> in the sidebar.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        events = st.session_state.events_feed

        # Score header
        if st.session_state.active_feed:
            meta = st.session_state.active_feed.metadata
            goals = [e for e in events if e.event_type == EventType.GOAL]
            home_goals = len([g for g in goals if g.team == meta.home_team.name])
            away_goals = len([g for g in goals if g.team == meta.away_team.name])

            st.markdown(
                f'<div style="text-align:center;padding:16px;background:#f9fafb;'
                f'border-radius:8px;margin-bottom:16px;">'
                f'<span style="font-size:1.5rem;font-weight:700;">'
                f'{meta.home_team.name} {home_goals} - {away_goals} {meta.away_team.name}'
                f'</span></div>',
                unsafe_allow_html=True,
            )

        # Event list (newest first)
        events_html = ""
        for event in reversed(events):
            events_html += render_event(event)

        st.markdown(
            f'<div style="max-height:600px;overflow-y:auto;padding:8px;">'
            f'{events_html}</div>',
            unsafe_allow_html=True,
        )

# ── Analyst tab ────────────────────────────────────────────────────

with analyst_tab:
    if not st.session_state.match_loaded:
        st.markdown(
            '<div style="text-align:center;padding:60px;color:#9ca3af;">'
            '<p style="font-size:1.2rem;">Load a match first.</p>'
            '<p>The analyst needs match data to work with.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        # Chat history display
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                sr = msg.get("structured_response", {})
                if sr.get("evidence"):
                    with st.expander(f"📋 Evidence ({len(sr['evidence'])} items)"):
                        for e in sr["evidence"]:
                            player_tag = f" ({e.get('player', '')})" if e.get("player") else ""
                            st.markdown(f"- **{e.get('minute', '?')}'**{player_tag}: {e.get('description', '')}")
                        conf = sr.get("confidence", "medium")
                        conf_icons = {"high": "🟢", "medium": "🟡", "low": "🔴"}
                        st.caption(f"{conf_icons.get(conf, '⚪')} Confidence: {conf} | Sources: {', '.join(sr.get('sources', []))}")

        # Chat input
        if question := st.chat_input("Ask the analyst about the match..."):
            # Add user message
            st.session_state.chat_history.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            # Get agent response
            with st.chat_message("assistant"):
                with st.spinner("Analysing..."):
                    match_id = st.session_state.active_match_id or "match_001"
                    result = st.session_state.agent.invoke(
                        input={
                            "question": question,
                            "match_id": match_id,
                            "retries": 0,
                        }
                    )

                    sr = result.get("structured_response", {})
                    sources = result.get("sources", [])

                    # Render structured answer
                    answer = sr.get("answer", result.get("generation", "I couldn't generate an analysis."))
                    st.markdown(answer)

                    # Evidence block
                    evidence = sr.get("evidence", [])
                    if evidence:
                        st.markdown("**Evidence:**")
                        for e in evidence:
                            player_tag = f" ({e.get('player', '')})" if e.get("player") else ""
                            st.markdown(f"- **{e.get('minute', '?')}'**{player_tag}: {e.get('description', '')}")

                    # Confidence + Sources
                    col_conf, col_src = st.columns(2)
                    with col_conf:
                        confidence = sr.get("confidence", "medium")
                        conf_colors = {"high": "🟢", "medium": "🟡", "low": "🔴"}
                        st.markdown(f"**Confidence:** {conf_colors.get(confidence, '⚪')} {confidence}")
                    with col_src:
                        data_sources = sr.get("sources", [])
                        if data_sources:
                            st.markdown(f"**Sources:** {', '.join(data_sources)}")

                    # Retrieval trace
                    if sources:
                        with st.expander("🔎 Retrieval trace"):
                            for src in sources:
                                if src.get("type") == "tool_result":
                                    st.markdown(f"🔧 Tool: `{src.get('tool', 'N/A')}` — args: `{src.get('args', {})}`")
                                elif src.get("event_id"):
                                    st.markdown(
                                        f"🔍 **{src.get('minute', '?')}' — "
                                        f"{src.get('event_type', 'event').replace('_', ' ').title()}**"
                                        f" ({src.get('player_name', '')})"
                                    )

                    # Save to history
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer,
                        "structured_response": sr,
                        "sources": sources,
                    })
