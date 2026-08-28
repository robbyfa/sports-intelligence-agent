# 03 — Streaming Layer (`streaming/`)

This package simulates a Kafka event pipeline without requiring a real broker. It has four files.

## `mock_kafka.py` — The Fake Broker

Three classes that mimic a Kafka broker using Python's `queue.Queue`:

### `TopicRegistry`

A shared registry that maps topic names to queues. Thread-safe (uses a `threading.Lock`). Both producers and consumers reference the same registry.

```python
registry = TopicRegistry()
# Both producer and consumer share this registry
```

### `MockProducer`

Mirrors `confluent_kafka.Producer`. Has one main method:

- `produce(topic, value, key=None)` — serializes the value (accepts `dict`, `str`, or `bytes`) and pushes a `Message` onto the topic's queue.

### `MockConsumer`

Mirrors `confluent_kafka.Consumer`:

- `subscribe(topic)` — binds to a topic's queue
- `poll(timeout)` — blocks up to `timeout` seconds waiting for a message. Returns `None` if nothing arrives.

### `Message`

A dataclass holding `topic`, `value` (bytes), `key`, `timestamp`, and `offset`. Has a `value_json()` helper for deserialization.

**Why this design?** The API surface mirrors Confluent's Python client closely enough that swapping to a real Kafka broker later is a find-and-replace exercise, not an architecture change.

## `producer.py` — Pushes Match Events

`MatchEventProducer` takes a `MockProducer` and a `MatchFeed`, then publishes events in one of two modes:

- **`produce_batch(feed)`** — pushes all events instantly. Used for testing and quick demos.
- **`produce_realtime(feed, speed_multiplier)`** — introduces delays proportional to the time gaps between events. A `speed_multiplier` of 100 means a 90-minute match plays out in about 54 seconds.

Both methods accept an `on_event` callback that fires after each event is produced (used by the Streamlit UI).

Events are serialized as JSON via Pydantic's `model_dump_json()` and keyed by `match_id`.

## `consumer.py` — Reads Typed Events

`EventConsumer` wraps `MockConsumer` and adds deserialization:

- `poll(timeout)` — returns a single `MatchEvent` or `None`
- `consume(timeout, max_empty_polls)` — a generator that yields `MatchEvent` objects until the queue is drained (stops after N consecutive empty polls)

## `pipeline.py` — The Glue

`IngestionPipeline` connects the consumer to both storage backends. It's the central piece that wires streaming to storage.

### Three ways to use it:

1. **`run(metadata)`** — consumes from an external producer/consumer pair and writes each event to SQLite + Chroma. Used when you want separate control over production and consumption.

2. **`ingest_event(event, metadata)`** — ingests a single event directly, no consumer needed. Used by the Streamlit real-time mode where events arrive one at a time from a background thread.

3. **`ingest_match(feed)`** — convenience method that creates an internal producer/consumer pair, produces all events in batch, consumes them, and writes to both stores. One-liner for tests and demos.

### What happens to each event:

1. **Normalise** — strip whitespace, ensure narrative_text is non-empty
2. **Track score** — if the event is a goal, update the running score dict
3. **Write to SQLite** — `event_store.insert_event(event)`
4. **Write to Chroma** — `vector_store.index_event(event, metadata, score_state)` — the current score is baked into the embedded document so semantic search results carry score context
