"""End-to-end tests for the ingestion pipeline.

Produces fixture events → consumes → verifies data lands in both SQLite and Chroma.
"""

import os
from unittest.mock import MagicMock

import pytest
from dotenv import load_dotenv

load_dotenv()

from fixtures import load_fixture
from models.events import EventType, MatchFeed
from storage.event_store import EventStore
from storage.vector_store import SportVectorStore
from streaming.pipeline import IngestionPipeline
from streaming.mock_kafka import MockConsumer, MockProducer, TopicRegistry
from streaming.producer import MatchEventProducer
from streaming.consumer import EventConsumer

needs_openai = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)


@pytest.fixture
def feed() -> MatchFeed:
    return load_fixture("match_001")


@pytest.fixture
def event_store() -> EventStore:
    store = EventStore(":memory:")
    yield store
    store.close()


@pytest.fixture
def vector_store() -> SportVectorStore:
    store = SportVectorStore(collection_name="test-pipeline")
    yield store
    store.reset()


# ── ingest_match (batch convenience method) ────────────────────────

@needs_openai
def test_ingest_match_writes_to_sqlite(feed, event_store, vector_store):
    pipeline = IngestionPipeline(event_store, vector_store)
    count = pipeline.ingest_match(feed)

    assert count == len(feed.events)

    # Verify SQLite has the data
    events = event_store.get_all_events("match_001")
    assert len(events) == len(feed.events)

    # Match metadata is there
    summary = event_store.get_match_summary("match_001")
    assert summary["home_team"] == "Arsenal"


@needs_openai
def test_ingest_match_writes_to_chroma(feed, event_store, vector_store):
    pipeline = IngestionPipeline(event_store, vector_store)
    pipeline.ingest_match(feed)

    # Verify Chroma has the data
    docs = vector_store.search("goal", match_id="match_001", k=3)
    assert len(docs) > 0


@needs_openai
def test_ingest_match_returns_correct_count(feed, event_store, vector_store):
    pipeline = IngestionPipeline(event_store, vector_store)
    count = pipeline.ingest_match(feed)
    assert count == len(feed.events)
    assert pipeline.events_ingested == len(feed.events)


@needs_openai
def test_ingest_match_calls_on_event_callback(feed, event_store, vector_store):
    pipeline = IngestionPipeline(event_store, vector_store)
    callback = MagicMock()
    pipeline.ingest_match(feed, on_event=callback)
    assert callback.call_count == len(feed.events)


# ── run() with external producer/consumer ──────────────────────────

@needs_openai
def test_run_with_external_producer_consumer(feed, event_store, vector_store):
    registry = TopicRegistry()
    producer = MockProducer(registry)
    consumer = MockConsumer(registry)
    ec = EventConsumer(consumer)

    # Produce first
    ep = MatchEventProducer(producer)
    ep.produce_batch(feed)

    # Then consume via pipeline
    pipeline = IngestionPipeline(event_store, vector_store, consumer=ec)
    count = pipeline.run(feed.metadata, timeout=0.1, max_empty_polls=2)

    assert count == len(feed.events)

    # Both stores have data
    assert len(event_store.get_all_events("match_001")) == len(feed.events)
    docs = vector_store.search("penalty", match_id="match_001", k=2)
    assert len(docs) > 0

    ec.close()
    registry.reset()


# ── run() without consumer raises ──────────────────────────────────

def test_run_without_consumer_raises(event_store, vector_store, feed):
    pipeline = IngestionPipeline(event_store, vector_store)
    with pytest.raises(RuntimeError, match="No consumer"):
        pipeline.run(feed.metadata)


# ── ingest_event (single-event mode) ──────────────────────────────

@needs_openai
def test_ingest_event_single(feed, event_store, vector_store):
    pipeline = IngestionPipeline(event_store, vector_store)
    event = feed.events[0]
    pipeline.ingest_event(event, feed.metadata)

    assert pipeline.events_ingested == 1
    events = event_store.get_all_events("match_001")
    assert len(events) == 1


# ── Score tracking ─────────────────────────────────────────────────

@needs_openai
def test_score_tracking_through_pipeline(feed, event_store, vector_store):
    """After full ingestion, the match summary score should be correct."""
    pipeline = IngestionPipeline(event_store, vector_store)
    pipeline.ingest_match(feed)

    summary = event_store.get_match_summary("match_001")
    assert summary["score"]["home"] == 2  # Arsenal
    assert summary["score"]["away"] == 1  # Man City


# ── Normalisation ──────────────────────────────────────────────────

@needs_openai
def test_normalisation_strips_whitespace(event_store, vector_store, feed):
    """Events with extra whitespace get cleaned up."""
    pipeline = IngestionPipeline(event_store, vector_store)
    event = feed.events[0].model_copy(
        update={"narrative_text": "  Leading whitespace and trailing  "}
    )
    pipeline.ingest_event(event, feed.metadata)

    stored = event_store.get_all_events("match_001")
    assert stored[0].narrative_text == "Leading whitespace and trailing"
