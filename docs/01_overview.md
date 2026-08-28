# 01 — Project Overview

## What This Project Does

This is a **streaming sports intelligence agent**. It ingests live-style sports events (goals, cards, substitutions, etc.) through a Kafka-like pipeline, stores them in two backends (SQLite for structured queries, Chroma for semantic search), and uses a LangGraph agent to answer analytical questions about matches with evidence-grounded responses.

Think of it as an AI-powered post-match pundit that can:
- Summarise a match
- Analyse what happened after a red card or substitution
- Tell you which player had the biggest impact
- Pull specific events from a time range
- Generate an analyst brief backed by real event data

## How It All Fits Together

```
fixtures/match_001.json        <-- static match data (the "source of truth")
        |
  [Mock Kafka Producer]        <-- pushes events to an in-memory queue
        |
  [Mock Kafka Consumer]        <-- pulls events off the queue
        |
  [Ingestion Pipeline]         <-- normalises events, writes to both stores
        |
  +-------------------+
  |  SQLite            |       <-- structured data: "give me goals from min 60-75"
  |  Chroma            |       <-- semantic data: "what was the turning point?"
  +-------------------+
        |
  [LangGraph Agent]            <-- routes questions, calls tools, generates answers
        |
  [Streamlit UI]               <-- user interface with live feed + chat
```

## Key Design Choices

1. **Dual storage** — SQLite handles precise, structured queries (timeline, stats). Chroma handles fuzzy, semantic queries (narrative search). The agent picks the right one via an LLM-powered router.

2. **Mock Kafka** — Uses Python `queue.Queue` to simulate Kafka topics. The producer/consumer API mirrors Confluent's client so you can swap it for a real broker later without changing application code.

3. **Quality loop** — Every generated answer goes through hallucination detection and answer grading. If the response isn't grounded in the data or doesn't answer the question, the agent retries (up to 3 times).

4. **Sport-agnostic schema** — The event models use a flexible `additional_info` dict for sport-specific data. Adding NFL or basketball events means adding new `EventType` values, not rewriting the schema.

## Running It

```bash
# Streamlit UI (recommended)
streamlit run app.py

# CLI mode
python main.py
```

## File Count

- **47 source files** across 7 packages
- **113 tests** covering models, streaming, storage, tools, chains, and full integration
