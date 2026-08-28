"""Tests for the mock Kafka streaming layer."""

import time
from unittest.mock import MagicMock

import pytest

from fixtures import load_fixture
from models.events import EventType, MatchEvent
from streaming.mock_kafka import MockConsumer, MockProducer, TopicRegistry
from streaming.producer import MatchEventProducer
from streaming.consumer import EventConsumer


@pytest.fixture
def registry():
    r = TopicRegistry()
    yield r
    r.reset()


@pytest.fixture
def feed():
    return load_fixture("match_001")


# ── TopicRegistry ──────────────────────────────────────────────────

def test_registry_creates_topic(registry):
    q = registry.get_or_create("test_topic")
    assert q is not None
    # Same reference on second call
    assert registry.get_or_create("test_topic") is q


def test_registry_offsets(registry):
    registry.get_or_create("t1")
    assert registry.next_offset("t1") == 0
    assert registry.next_offset("t1") == 1
    assert registry.next_offset("t1") == 2


def test_registry_reset(registry):
    registry.get_or_create("t1")
    registry.next_offset("t1")
    registry.reset()
    # After reset, fresh offset
    registry.get_or_create("t1")
    assert registry.next_offset("t1") == 0


# ── MockProducer / MockConsumer ────────────────────────────────────

def test_produce_and_consume_bytes(registry):
    producer = MockProducer(registry)
    consumer = MockConsumer(registry)
    consumer.subscribe("test")

    producer.produce("test", value=b'{"hello": "world"}')
    msg = consumer.poll(timeout=0.5)

    assert msg is not None
    assert msg.value == b'{"hello": "world"}'
    assert msg.topic == "test"
    assert msg.offset == 0


def test_produce_dict_auto_serialized(registry):
    producer = MockProducer(registry)
    consumer = MockConsumer(registry)
    consumer.subscribe("test")

    producer.produce("test", value={"foo": "bar"})
    msg = consumer.poll(timeout=0.5)
    assert msg.value_json() == {"foo": "bar"}


def test_produce_string_auto_encoded(registry):
    producer = MockProducer(registry)
    consumer = MockConsumer(registry)
    consumer.subscribe("test")

    producer.produce("test", value='plain text')
    msg = consumer.poll(timeout=0.5)
    assert msg.value == b"plain text"


def test_poll_returns_none_when_empty(registry):
    consumer = MockConsumer(registry)
    consumer.subscribe("test")
    msg = consumer.poll(timeout=0.1)
    assert msg is None


def test_poll_raises_if_not_subscribed(registry):
    consumer = MockConsumer(registry)
    with pytest.raises(RuntimeError, match="not subscribed"):
        consumer.poll()


def test_message_ordering(registry):
    producer = MockProducer(registry)
    consumer = MockConsumer(registry)
    consumer.subscribe("test")

    for i in range(10):
        producer.produce("test", value={"i": i})

    for i in range(10):
        msg = consumer.poll(timeout=0.5)
        assert msg is not None
        assert msg.value_json()["i"] == i
        assert msg.offset == i


# ── MatchEventProducer ─────────────────────────────────────────────

def test_produce_batch_all_events(registry, feed):
    producer = MockProducer(registry)
    consumer = MockConsumer(registry)
    consumer.subscribe("sports_events")

    ep = MatchEventProducer(producer)
    count = ep.produce_batch(feed)

    assert count == len(feed.events)

    # Consume all and verify
    consumed = []
    for _ in range(count):
        msg = consumer.poll(timeout=0.5)
        assert msg is not None
        event = MatchEvent.model_validate_json(msg.value)
        consumed.append(event)

    assert len(consumed) == count
    # First event should be kick_off (earliest by minute)
    assert consumed[0].event_type == EventType.KICK_OFF


def test_produce_batch_calls_on_event_callback(registry, feed):
    producer = MockProducer(registry)
    ep = MatchEventProducer(producer)

    callback = MagicMock()
    ep.produce_batch(feed, on_event=callback)

    assert callback.call_count == len(feed.events)


def test_produce_batch_events_ordered_by_minute(registry, feed):
    producer = MockProducer(registry)
    consumer = MockConsumer(registry)
    consumer.subscribe("sports_events")

    ep = MatchEventProducer(producer)
    count = ep.produce_batch(feed)

    prev_minute = -1
    for _ in range(count):
        msg = consumer.poll(timeout=0.5)
        event = MatchEvent.model_validate_json(msg.value)
        assert event.minute >= prev_minute
        prev_minute = event.minute


def test_produce_realtime_has_delay(registry, feed):
    """Verify real-time mode introduces delays (using high speed multiplier)."""
    producer = MockProducer(registry)
    ep = MatchEventProducer(producer)

    # Use very high speed so it doesn't take forever, but there's still some delay
    start = time.monotonic()
    count = ep.produce_realtime(feed, speed_multiplier=10000.0)
    elapsed = time.monotonic() - start

    assert count == len(feed.events)
    # Even at 10000x speed, a 93-minute match should take at least a tiny delay
    assert elapsed > 0


def test_produce_realtime_rejects_zero_speed(registry, feed):
    producer = MockProducer(registry)
    ep = MatchEventProducer(producer)
    with pytest.raises(ValueError, match="speed_multiplier"):
        ep.produce_realtime(feed, speed_multiplier=0)


# ── EventConsumer ──────────────────────────────────────────────────

def test_event_consumer_yields_typed_events(registry, feed):
    producer = MockProducer(registry)
    ep = MatchEventProducer(producer)
    ep.produce_batch(feed)

    consumer = MockConsumer(registry)
    ec = EventConsumer(consumer)

    events = list(ec.consume(timeout=0.1, max_empty_polls=2))
    assert len(events) == len(feed.events)
    assert all(isinstance(e, MatchEvent) for e in events)


def test_event_consumer_stops_after_empty_polls(registry):
    """Consumer stops after max_empty_polls consecutive empties."""
    consumer = MockConsumer(registry)
    ec = EventConsumer(consumer, topic="empty_topic")

    start = time.monotonic()
    events = list(ec.consume(timeout=0.05, max_empty_polls=2))
    elapsed = time.monotonic() - start

    assert len(events) == 0
    # Should have waited roughly 2 * 0.05s
    assert elapsed < 1.0


def test_event_consumer_close(registry):
    consumer = MockConsumer(registry)
    ec = EventConsumer(consumer, topic="test")
    ec.close()
    # After close, underlying consumer is unsubscribed
    assert consumer._subscribed_topic is None
