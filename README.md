# ⚽ Streaming Sports Intelligence Agent

> Built a streaming sports intelligence agent using Kafka, LangChain, LangGraph and RAG to ingest live-style sports events, retrieve fresh context, call structured tools, and generate evidence-grounded match analysis with claim verification.

Sport-agnostic architecture, football/soccer examples first. Every answer comes with cited evidence, confidence scoring, and source attribution.

---

## Architecture

```
Mock Event Producer
       │
       ▼
┌──────────────────┐
│  Kafka Topic     │   In-process mock (queue.Queue)
│  sports_events   │   Swappable for Confluent Kafka
└──────┬───────────┘
       │
  Event Consumer
       │
  Normaliser
       │
       ▼
┌──────────────────────────────────┐
│  SQLite          │  Chroma       │
│  (structured     │  (semantic    │
│   queries)       │   retrieval)  │
└──────────────────┴───────────────┘
       │                  │
       ▼                  ▼
┌──────────────────────────────────┐
│         LangGraph Agent          │
│  route → tools/search/brief      │
│  → grade → generate              │
│  → hallucination check           │
│  → answer check → sources        │
└──────────────────────────────────┘
       │
       ▼
   Streamlit UI (3-column)
```

### LangGraph Workflow

![Agent Graph](graph.png)

The agent has **4 entry routes**, chosen by an LLM-powered router:

| Route | When | What happens |
|-------|------|-------------|
| **Tool Execute** | Specific queries (timeline, stats, summary) | LLM picks tools → execute → grade → generate |
| **Event Search** | Narrative questions ("turning point?") | Semantic search over Chroma → grade → generate |
| **Analyst Brief** | Comprehensive analysis requests | 5-step workflow with claim verification → END |
| **Web Search** | Off-topic questions | Tavily web search → generate |

After generation, a **quality loop** checks:
1. Is the answer grounded in the evidence? (hallucination grader)
2. Does it actually answer the question? (answer grader)
3. If not → retry with different context (max 3 retries)

### Kafka Topic Design

```
Topic: sports_events
  Key:   match_id (e.g. "match_001")
  Value: JSON-serialised MatchEvent
  
  Modes:
    batch    → all events pushed instantly
    realtime → events drip in proportional to match time
               (configurable speed multiplier)
```

The mock Kafka uses Python `queue.Queue` with a `TopicRegistry`, `MockProducer`, and `MockConsumer` that mirror the Confluent Kafka API surface — swap to a real broker by changing the import.

---

## Structured Output

Every response follows this format:

```
Answer:
Arsenal became more direct after the 61st-minute substitution.
Trossard's introduction shifted the balance of play decisively.

Evidence:
  - 63' (Leandro Trossard): Replaced Zinchenko; more attacking option on the left
  - 67' (Martin Odegaard): Arsenal dominating midfield with extra-man advantage
  - 76' (Bukayo Saka): Equaliser via Odegaard reverse pass

Confidence: high
Sources: match_events, player_stats
```

The **Analyst Brief** workflow adds claim verification:

```
Claim Verification: 6/6 claims supported
  ✓ Arsenal defeated Manchester City 2-1 at the Emirates Stadium.
  ✓ Bukayo Saka scored both goals for Arsenal in the second half.
  ✓ Erling Haaland scored the opening goal in the 37th minute.
  ✓ Rodri received a red card in the 58th minute.
  ✓ Saka equalised in the 76th minute.
  ✓ Saka converted a penalty in the 90th minute.
```

---

## Analyst Brief Workflow

The showcase "agentic" feature — a multi-step pipeline triggered by questions like *"Generate a post-match analyst brief"*:

```
Step 1: Retrieve full match timeline (SQLite)
   │
Step 2: Get top-5 player impact stats (SQLite)
   │
Step 3: Identify tactical turning points (Chroma semantic search)
   │
Step 4: Generate structured analyst brief (LLM structured output)
   │
Step 5: Extract factual claims → verify each against source data
   │
   ▼
Final brief with per-claim verification scores
```

Every factual claim in the brief is independently verified against the source data. The confidence score is adjusted based on the verification pass rate.

---

## Evaluation Framework

20 test questions across 8 categories, evaluated on 5 dimensions:

| Dimension | Method | What it measures |
|-----------|--------|-----------------|
| Retrieval relevance | LLM judge | Are the right documents fetched? |
| Groundedness | LLM judge | Is the answer supported by evidence? |
| Citation quality | Regex + keyword | Does it cite specific minutes and players? |
| Tool selection | Route comparison | Did the router pick the correct path? |
| Event freshness | Minute detection | Are key match moments referenced? |

```bash
# Run all 20 evaluations
python -m evals.run_evals

# Run a single question
python -m evals.run_evals --question q06

# Run by category
python -m evals.run_evals --category narrative

# Export results to JSON
python -m evals.run_evals --output results.json
```

Enable LangSmith tracing by setting:
```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-...
LANGCHAIN_PROJECT=sports-intelligence-evals
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Event streaming | Mock Kafka (`queue.Queue`, Confluent-compatible API) |
| Structured storage | SQLite (timeline, stats, summary queries) |
| Semantic storage | Chroma + OpenAI embeddings |
| Agent framework | LangGraph (state machine, routing, quality loop) |
| LLM | OpenAI gpt-4o-mini (structured output) |
| Tools | LangChain `@tool` (timeline, player stats, match summary, event search) |
| Quality control | Retrieval grading, hallucination detection, answer grading |
| Evaluation | Custom 5-dimension eval framework + LangSmith tracing |
| UI | Streamlit (3-column layout) |
| Data models | Pydantic v2 |

---

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- OpenAI API key

### Install

```bash
git clone https://github.com/robbyfa/sports-intelligence-agent.git
cd sports-intelligence-agent
uv sync
```

### Environment

Create a `.env` file:

```
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...          # optional, for web search fallback
LANGCHAIN_API_KEY=ls-...         # optional, for LangSmith tracing
```

### Run

```bash
# Streamlit UI (recommended)
streamlit run app.py

# CLI with sample questions
python main.py

# Run evaluations
python -m evals.run_evals
```

**Streamlit workflow:**
1. Select a match fixture in the sidebar
2. Choose Batch (instant) or Real-time (events stream in)
3. Click **Start Match**
4. Ask questions in the middle column
5. See evidence + sources + trace in the right column

---

## Example Questions

| Question | Route | What you get |
|----------|-------|-------------|
| What happened between minute 60 and 75? | Tools | Timeline of events in that window |
| How did Saka play? | Tools | Aggregated stats + key moments |
| What's the score? | Tools | Full match summary |
| What was the turning point? | Vector search | Narrative analysis with cited events |
| What changed after the red card? | Vector search | Impact analysis with evidence |
| Generate a post-match analyst brief | Analyst brief | Multi-step analysis + claim verification |

---

## Project Structure

```
.
├── app.py                          # Streamlit UI (3-column layout)
├── main.py                         # CLI entry point
├── pyproject.toml                  # Dependencies
├── graph.png                       # LangGraph workflow diagram
│
├── models/
│   ├── events.py                   # Pydantic: Player, MatchEvent, MatchFeed (16 event types)
│   └── analysis.py                 # Pydantic: StructuredAnalysis, EvidenceItem, Confidence
│
├── fixtures/
│   └── match_001.json              # Arsenal 2-1 Man City (36 events, all types)
│
├── streaming/
│   ├── mock_kafka.py               # TopicRegistry, MockProducer, MockConsumer
│   ├── producer.py                 # Batch + real-time modes
│   ├── consumer.py                 # Typed event consumer
│   └── pipeline.py                 # Consumer → SQLite + Chroma with score tracking
│
├── storage/
│   ├── event_store.py              # SQLite: timeline, player stats, match summary queries
│   └── vector_store.py             # Chroma: score-aware embeddings, metadata filters
│
├── graph/
│   ├── state.py                    # GraphState (question, generation, structured_response, ...)
│   ├── graph.py                    # LangGraph state machine (4 routes, quality loop)
│   ├── chains/
│   │   ├── router.py               # 4-way router (tools/vectorstore/analyst_brief/websearch)
│   │   ├── generation.py           # Structured output + plain text generation chains
│   │   ├── retrieval_grader.py     # Document relevance grader
│   │   ├── hallucination_grader.py # Grounding checker
│   │   └── answer_grader.py        # Answer quality checker
│   ├── nodes/
│   │   ├── tool_execute.py         # LLM-driven tool dispatch
│   │   ├── event_search.py         # Chroma semantic search
│   │   ├── analyst_brief.py        # Multi-step analyst brief workflow
│   │   ├── generate.py             # Structured generation with fallback
│   │   ├── grade_documents.py      # Relevance filtering
│   │   └── web_search.py           # Tavily fallback
│   ├── tools/
│   │   ├── timeline_tool.py        # Events in a minute range
│   │   ├── player_stats_tool.py    # Aggregated player statistics
│   │   ├── match_summary_tool.py   # Score, lineups, cards, subs
│   │   └── event_search_tool.py    # Semantic event search
│   └── workflows/
│       └── analyst_brief.py        # 5-step brief: gather → stats → tactics → generate → verify
│
├── evals/
│   ├── dataset.py                  # 20 test questions, 8 categories
│   ├── evaluators.py               # 5 evaluation dimensions
│   └── run_evals.py                # CLI eval runner with summary tables
│
├── tests/                          # 113+ tests (models, streaming, storage, tools, graph)
└── docs/                           # Module-level documentation (8 files)
```

---

## Testing

```bash
# Unit tests (no API key needed)
pytest tests/test_models.py tests/test_streaming.py tests/test_event_store.py -v

# Integration tests (needs OPENAI_API_KEY)
pytest tests/test_graph.py tests/test_tools.py tests/test_vector_store.py -v

# All tests
pytest -v
```

---

## Design Decisions

**Dual storage.** SQLite for precise queries ("goals from minute 60-75"), Chroma for fuzzy queries ("what was the turning point?"). The agent picks the right backend via the router.

**Mock Kafka.** Uses `queue.Queue` internally but exposes a Confluent-compatible API (`produce`, `subscribe`, `poll`). Swap to a real broker by changing the import — no application code changes.

**Structured output.** The LLM produces `StructuredAnalysis` objects via `with_structured_output()`, ensuring every response includes evidence items, confidence, and source attribution. Falls back to plain text if structured output fails.

**Quality loop with retry limit.** Hallucination and answer grading catch bad generations. Max 3 retries prevents infinite loops. The analyst brief workflow skips this loop — it has its own claim verification.

**Claim verification.** The analyst brief extracts factual claims from the generated text and verifies each one independently against the source data. Confidence is adjusted based on the verification pass rate.

**Sport-agnostic schema.** The `EventType` enum and `additional_info` dict accommodate any sport. Add NFL events by adding new enum values, not by rewriting the schema.

---

## Limitations

- **Mock data only.** The fixture is a single synthetic match. Production use would need real event feeds.
- **No persistent vector store.** Chroma runs in-memory in the Streamlit app. Events are re-indexed on every restart.
- **Single-match scope.** The agent analyses one match at a time. No cross-match comparison.
- **LLM cost.** The quality loop can make 3-5 LLM calls per question. The analyst brief makes 8-10. No caching layer.
- **No authentication.** The Streamlit app has no user auth or rate limiting.

## Future Improvements

- **Real Kafka broker** via Docker Compose with Confluent or Redpanda
- **Live data feeds** from sports APIs (Opta, StatsBomb, football-data.org)
- **NFL / basketball events** using the same schema with sport-specific event types
- **PostgreSQL** replacing SQLite for concurrent access
- **Hosted Chroma** or Pinecone for persistent vector storage
- **LangSmith dashboard** for production monitoring and eval tracking
- **Multi-match analysis** — compare player performance across fixtures
- **Response caching** to reduce LLM costs on repeated questions
