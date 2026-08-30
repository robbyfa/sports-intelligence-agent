"""Streamlit UI for the Streaming Sports Intelligence Agent.

2-column layout:
  Left:  Ingested match events (live feed)
  Right: Chat with the analyst (evidence + sources embedded in each reply)

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
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────

st.markdown("""
<style>
    .block-container { padding-top: 2.5rem; }
    .event-feed { max-height: 75vh; overflow-y: auto; padding: 0.5rem; }
    .score-header {
        text-align: center; padding: 12px; background: rgba(128,128,128,0.15);
        border-radius: 8px; margin-bottom: 12px; font-size: 1.3rem; font-weight: 700;
    }
    .evidence-item {
        padding: 6px 10px; margin: 4px 0;
        background: rgba(34, 197, 94, 0.08);
        border-left: 3px solid #22c55e; border-radius: 4px; font-size: 0.85rem;
        color: inherit;
    }
    .claim-pass {
        border-left-color: #22c55e;
        background: rgba(34, 197, 94, 0.08);
        color: inherit;
    }
    .claim-fail {
        border-left-color: #ef4444;
        background: rgba(239, 68, 68, 0.08);
        color: inherit;
    }
    .trace-item {
        padding: 3px 8px; margin: 2px 0;
        background: rgba(128, 128, 128, 0.08);
        border-radius: 4px; font-size: 0.78rem;
        color: inherit; opacity: 0.75;
    }
    .conf-high { background: rgba(34, 197, 94, 0.15); color: #22c55e; }
    .conf-medium { background: rgba(234, 179, 8, 0.15); color: #eab308; }
    .conf-low { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
    .confidence-badge {
        display: inline-block; padding: 2px 10px; border-radius: 12px;
        font-size: 0.78rem; font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ── Event type styling ─────────────────────────────────────────────

EVENT_BADGES = {
    EventType.GOAL: ("⚽ GOAL", "#22c55e"),
    EventType.ASSIST: ("🅰️ ASSIST", "#3b82f6"),
    EventType.SUBSTITUTION: ("🔄 SUB", "#f59e0b"),
    EventType.YELLOW_CARD: ("🟨 YELLOW", "#eab308"),
    EventType.RED_CARD: ("🟥 RED", "#ef4444"),
    EventType.SHOT: ("🎯 SHOT", "#8b5cf6"),
    EventType.PASS_SEQUENCE: ("🔗 PASS", "#06b6d4"),
    EventType.FOUL: ("⚠️ FOUL", "#f97316"),
    EventType.CORNER: ("🚩 CORNER", "#6366f1"),
    EventType.FREE_KICK: ("🦶 FK", "#10b981"),
    EventType.PENALTY: ("🎯 PEN", "#ef4444"),
    EventType.VAR_DECISION: ("📺 VAR", "#ec4899"),
    EventType.TACTICAL_SHIFT: ("♟️ TACTICS", "#14b8a6"),
    EventType.HALF_TIME: ("⏸️ HT", "#6b7280"),
    EventType.FULL_TIME: ("🏁 FT", "#6b7280"),
    EventType.KICK_OFF: ("▶️ KO", "#6b7280"),
}


def render_event_compact(event: MatchEvent) -> str:
    label, color = EVENT_BADGES.get(event.event_type, ("📌 EVENT", "#6b7280"))
    player = f" — {event.player_name}" if event.player_name else ""
    return (
        f'<div style="padding:6px 0;border-bottom:1px solid rgba(128,128,128,0.2);font-size:0.85rem;">'
        f'<strong>{event.minute}\'</strong> '
        f'<span style="background:{color};color:white;padding:1px 6px;'
        f'border-radius:3px;font-size:0.7rem;font-weight:600;">{label}</span>'
        f'{player}'
        f'<br><span style="opacity:0.7;font-size:0.8rem;">{event.narrative_text[:120]}</span>'
        f'</div>'
    )


# ── Helper: render inline citations ───────────────────────────────

def render_citations(sr: dict, sources: list) -> None:
    """Render evidence, confidence, sources, and trace inline in a chat message."""
    evidence = sr.get("evidence", [])
    verifications = sr.get("claim_verifications", [])
    confidence = sr.get("confidence", "medium")
    data_sources = sr.get("sources", [])

    # Normalise confidence
    if isinstance(confidence, str):
        confidence = confidence.split(".")[-1].lower()

    # Evidence
    if evidence:
        with st.expander(f"📋 Evidence ({len(evidence)} items)", expanded=False):
            for e in evidence:
                player_tag = f" ({e.get('player', '')})" if e.get("player") else ""
                st.markdown(
                    f'<div class="evidence-item">'
                    f'<strong>{e.get("minute", "?")}\'</strong>{player_tag}: '
                    f'{e.get("description", "")}</div>',
                    unsafe_allow_html=True,
                )

    # Claim verifications
    if verifications:
        verified = sr.get("verified_claims", 0)
        total = sr.get("total_claims", 0)
        with st.expander(f"✅ Claim Verification ({verified}/{total} supported)", expanded=False):
            for v in verifications:
                css = "claim-pass" if v.get("supported") else "claim-fail"
                icon = "✓" if v.get("supported") else "✗"
                st.markdown(
                    f'<div class="evidence-item {css}">{icon} {v.get("claim", "")}</div>',
                    unsafe_allow_html=True,
                )

    # Confidence + data sources (inline row)
    conf_class = f"conf-{confidence}" if confidence in ("high", "medium", "low") else ""
    meta_parts = [f'<span class="confidence-badge {conf_class}">Confidence: {confidence}</span>']
    if data_sources:
        meta_parts.append(f'<span style="opacity:0.6;font-size:0.78rem;margin-left:12px;">📁 {", ".join(data_sources)}</span>')
    st.markdown(" ".join(meta_parts), unsafe_allow_html=True)

    # Retrieval trace
    if sources:
        with st.expander("🔎 Retrieval trace", expanded=False):
            for src in sources:
                if src.get("type") == "tool_result":
                    st.markdown(
                        f'<div class="trace-item">🔧 <code>{src.get("tool", "?")}</code>'
                        f' — {src.get("args", {})}</div>',
                        unsafe_allow_html=True,
                    )
                elif src.get("event_id"):
                    etype = src.get("event_type", "event").replace("_", " ").title()
                    st.markdown(
                        f'<div class="trace-item">🔍 {src.get("minute", "?")}\'  '
                        f'{etype} — {src.get("player_name", "")}</div>',
                        unsafe_allow_html=True,
                    )


# ── Session state ──────────────────────────────────────────────────

def init_session_state():
    defaults = {
        "event_store": None,
        "vector_store": None,
        "agent": None,
        "match_loaded": False,
        "match_status": "not_started",
        "events_feed": [],
        "chat_history": [],
        "active_match_id": None,
        "active_feed": None,
        "ingestion_complete": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session_state()


# ── Store + agent setup ───────────────────────────────────────────

def setup_stores():
    if st.session_state.event_store is None:
        st.session_state.event_store = EventStore(":memory:")
    if st.session_state.vector_store is None:
        st.session_state.vector_store = SportVectorStore(collection_name="sports-events-ui")


def setup_agent():
    configure(
        event_store=st.session_state.event_store,
        vector_store=st.session_state.vector_store,
    )
    if st.session_state.agent is None:
        st.session_state.agent = build_graph()


# ── Ingestion ──────────────────────────────────────────────────────

def ingest_batch(feed: MatchFeed):
    setup_stores()
    pipeline = IngestionPipeline(st.session_state.event_store, st.session_state.vector_store)
    events_list: list[MatchEvent] = []
    pipeline.ingest_match(feed, on_event=lambda e: events_list.append(e))
    st.session_state.events_feed = events_list
    st.session_state.match_loaded = True
    st.session_state.match_status = "complete"
    st.session_state.active_match_id = feed.metadata.match_id
    st.session_state.active_feed = feed
    st.session_state.ingestion_complete = True
    setup_agent()


def _realtime_worker(feed, speed, event_store, vector_store, events_feed, status_box):
    pipeline = IngestionPipeline(event_store, vector_store)
    pipeline._metadata = feed.metadata
    events = feed.events_by_minute()
    prev = 0.0
    for event in events:
        cur = event.minute * 60 + event.second
        gap = cur - prev
        if gap > 0:
            time.sleep(gap / speed)
        prev = cur
        pipeline.ingest_event(event, feed.metadata)
        events_feed.append(event)
    status_box["done"] = True


def start_realtime(feed: MatchFeed, speed: float):
    setup_stores()
    st.session_state.event_store.insert_match(feed.metadata)
    st.session_state.match_loaded = True
    st.session_state.match_status = "in_progress"
    st.session_state.active_match_id = feed.metadata.match_id
    st.session_state.active_feed = feed
    st.session_state.ingestion_complete = False
    st.session_state.events_feed = []
    setup_agent()
    status_box = {"done": False}
    st.session_state["_rt_status_box"] = status_box
    thread = threading.Thread(
        target=_realtime_worker,
        args=(feed, speed, st.session_state.event_store,
              st.session_state.vector_store, st.session_state.events_feed, status_box),
        daemon=True,
    )
    thread.start()


# ── Sidebar ────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚽ Sports Intelligence Agent")
    st.caption("Kafka → RAG → LangGraph → Evidence-grounded analysis")
    st.markdown("---")

    fixtures = list_fixtures()
    selected = st.selectbox("Match", fixtures, format_func=lambda x: x.replace("_", " ").title())
    mode = st.radio("Mode", ["Batch", "Real-time"], horizontal=True)
    speed = 100.0
    if mode == "Real-time":
        speed = st.slider("Speed", 10.0, 1000.0, 100.0, 10.0)

    col_start, col_clear = st.columns(2)
    with col_start:
        if st.button("▶️ Start Match", disabled=st.session_state.match_status == "in_progress",
                     use_container_width=True, type="primary"):
            st.session_state.events_feed = []
            st.session_state.chat_history = []
            st.session_state.match_loaded = False
            st.session_state.match_status = "not_started"
            st.session_state.ingestion_complete = False
            st.session_state.agent = None
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
    with col_clear:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

    st.markdown("---")
    status = st.session_state.match_status
    if status == "in_progress":
        sb = st.session_state.get("_rt_status_box", {})
        if sb.get("done"):
            st.session_state.match_status = "complete"
            st.session_state.ingestion_complete = True
            status = "complete"

    if status == "not_started":
        st.info("No match loaded")
    elif status == "in_progress":
        st.warning(f"⏳ In progress... ({len(st.session_state.events_feed)} events)")
        st.button("🔄 Refresh", use_container_width=True, on_click=lambda: None)
    elif status == "complete":
        st.success(f"✅ Complete ({len(st.session_state.events_feed)} events)")

    if st.session_state.active_feed:
        meta = st.session_state.active_feed.metadata
        st.markdown("---")
        st.markdown(f"**{meta.home_team.name}** vs **{meta.away_team.name}**")
        st.caption(f"{meta.competition} · {meta.venue} · {meta.date}")

    st.markdown("---")
    st.markdown("**Try asking:**")
    for q in [
        "Summarise the match",
        "What changed after the red card?",
        "Which player had the biggest impact?",
        "Generate a post-match analyst brief",
        "What happened between minute 60 and 80?",
        "How did Saka play?",
    ]:
        st.caption(f"→ {q}")


# ── Auto-refresh during real-time ──────────────────────────────────

if st.session_state.match_status == "in_progress":
    time.sleep(0.5)
    st.rerun()


# ── 2-Column Layout ───────────────────────────────────────────────

left_col, right_col = st.columns([1, 1.6])

# ── LEFT: Live Events ─────────────────────────────────────────────

with left_col:
    st.markdown("### 📡 Live Events")

    if not st.session_state.events_feed:
        st.caption("No events yet. Start a match from the sidebar.")
    else:
        events = st.session_state.events_feed

        if st.session_state.active_feed:
            meta = st.session_state.active_feed.metadata
            goals = [e for e in events if e.event_type == EventType.GOAL]
            hg = len([g for g in goals if g.team == meta.home_team.name])
            ag = len([g for g in goals if g.team == meta.away_team.name])
            st.markdown(
                f'<div class="score-header">{meta.home_team.short_name} {hg} — {ag} {meta.away_team.short_name}</div>',
                unsafe_allow_html=True,
            )

        html = "".join(render_event_compact(e) for e in reversed(events))
        st.markdown(f'<div class="event-feed">{html}</div>', unsafe_allow_html=True)

# ── RIGHT: Chat with the Analyst ──────────────────────────────────

with right_col:
    st.markdown("### 💬 Ask the Analyst")

    if not st.session_state.match_loaded:
        st.caption("Load a match first to start chatting.")
    else:
        # Scrollable chat container
        chat_container = st.container(height=550)

        with chat_container:
            # Render chat history with inline citations
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    # Render citations inline for assistant messages
                    if msg["role"] == "assistant":
                        sr = msg.get("structured_response", {})
                        sources = msg.get("sources", [])
                        if sr or sources:
                            render_citations(sr, sources)

        # Chat input (outside the container so it stays at the bottom)
        if question := st.chat_input("Ask about the match...", key="main_chat"):
            st.session_state.chat_history.append({"role": "user", "content": question})

            with st.spinner("Analysing..."):
                match_id = st.session_state.active_match_id or "match_001"
                result = st.session_state.agent.invoke(
                    input={"question": question, "match_id": match_id, "retries": 0}
                )
                sr = result.get("structured_response", {})
                answer = sr.get("answer", result.get("generation", "No analysis generated."))

                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": answer,
                    "structured_response": sr,
                    "sources": result.get("sources", []),
                })

            st.rerun()
