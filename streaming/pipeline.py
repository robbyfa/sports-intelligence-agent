"""Ingestion pipeline — connects the Kafka consumer to SQLite + Chroma.

Consumes events from the mock Kafka topic, normalises them, and writes
to both the SQLite event store (for structured queries) and the Chroma
vector store (for semantic retrieval).

Usage::

    pipeline = IngestionPipeline(event_store, vector_store, consumer)
    pipeline.run(match_metadata)

Or for a one-shot demo with a full match feed::

    pipeline = IngestionPipeline(event_store, vector_store)
    pipeline.ingest_match(feed)
"""

from __future__ import annotations

from typing import Callable, Optional

from models.events import EventType, MatchEvent, MatchFeed, MatchMetadata
from storage.event_store import EventStore
from storage.vector_store import SportVectorStore
from streaming.consumer import EventConsumer
from streaming.mock_kafka import MockConsumer, MockProducer, TopicRegistry
from streaming.producer import MatchEventProducer, SPORTS_EVENTS_TOPIC


class IngestionPipeline:
    """Connects the event consumer to both storage backends.

    Args:
        event_store: SQLite event store for structured queries.
        vector_store: Chroma vector store for semantic retrieval.
        consumer: Optional pre-configured event consumer. If not provided,
                  one is created internally when needed.
    """

    def __init__(
        self,
        event_store: EventStore,
        vector_store: SportVectorStore,
        consumer: Optional[EventConsumer] = None,
    ) -> None:
        self.event_store = event_store
        self.vector_store = vector_store
        self._consumer = consumer
        self._score: dict[str, int] = {"home": 0, "away": 0}
        self._metadata: Optional[MatchMetadata] = None
        self._events_ingested: int = 0

    @property
    def events_ingested(self) -> int:
        return self._events_ingested

    # ── Public API ─────────────────────────────────────────────────

    def run(
        self,
        match_metadata: MatchMetadata,
        on_event: Optional[Callable[[MatchEvent], None]] = None,
        timeout: float = 1.0,
        max_empty_polls: int = 3,
    ) -> int:
        """Consume events from the topic and write to both stores.

        Call this after a producer has started pushing events.
        Blocks until the consumer drains (``max_empty_polls`` consecutive
        empty polls).

        Args:
            match_metadata: Metadata for the match being ingested.
            on_event: Optional callback fired after each event is stored.
            timeout: Poll timeout per message.
            max_empty_polls: Stop after this many consecutive empty polls.

        Returns:
            Number of events ingested.
        """
        if self._consumer is None:
            raise RuntimeError(
                "No consumer configured. Pass one in the constructor or use ingest_match()."
            )

        self._metadata = match_metadata
        self._score = {"home": 0, "away": 0}
        self._events_ingested = 0

        # Insert match metadata into SQLite
        self.event_store.insert_match(match_metadata)

        for event in self._consumer.consume(timeout=timeout, max_empty_polls=max_empty_polls):
            normalised = self._normalise_event(event)
            self._ingest_single(normalised, match_metadata)
            if on_event:
                on_event(normalised)

        return self._events_ingested

    def ingest_event(
        self,
        event: MatchEvent,
        match_metadata: MatchMetadata,
    ) -> None:
        """Ingest a single event directly (no consumer needed).

        Useful for real-time mode where events arrive one at a time
        from the Streamlit UI thread.
        """
        if self._metadata is None:
            self._metadata = match_metadata
            self._score = {"home": 0, "away": 0}
            self.event_store.insert_match(match_metadata)

        normalised = self._normalise_event(event)
        self._ingest_single(normalised, match_metadata)

    def ingest_match(
        self,
        feed: MatchFeed,
        on_event: Optional[Callable[[MatchEvent], None]] = None,
    ) -> int:
        """Convenience: produce and consume a full match feed in one call.

        Creates an internal producer/consumer pair, pushes all events
        in batch mode, consumes them, and writes to both stores.

        Args:
            feed: Complete match feed.
            on_event: Optional callback fired after each event is stored.

        Returns:
            Number of events ingested.
        """
        registry = TopicRegistry()
        producer = MockProducer(registry)
        consumer = MockConsumer(registry)

        ep = MatchEventProducer(producer, topic=SPORTS_EVENTS_TOPIC)
        ec = EventConsumer(consumer, topic=SPORTS_EVENTS_TOPIC)

        # Store original consumer and swap temporarily
        original_consumer = self._consumer
        self._consumer = ec

        # Produce all events
        ep.produce_batch(feed)

        # Consume and ingest
        count = self.run(
            match_metadata=feed.metadata,
            on_event=on_event,
            timeout=0.1,
            max_empty_polls=2,
        )

        # Restore
        self._consumer = original_consumer
        ec.close()
        registry.reset()

        return count

    # ── Normalisation ──────────────────────────────────────────────

    def _normalise_event(self, event: MatchEvent) -> MatchEvent:
        """Validate and standardise an event before storage.

        - Strips whitespace from text fields.
        - Ensures narrative_text is non-empty.
        - Fills missing second field with 0.
        """
        narrative = event.narrative_text.strip() if event.narrative_text else ""
        if not narrative:
            narrative = (
                f"{event.event_type.value.replace('_', ' ').title()} "
                f"at minute {event.minute}"
            )
            if event.player_name:
                narrative += f" by {event.player_name}"

        player_name = event.player_name.strip() if event.player_name else None
        team = event.team.strip() if event.team else None

        return event.model_copy(
            update={
                "narrative_text": narrative,
                "player_name": player_name,
                "team": team,
            }
        )

    # ── Internal ───────────────────────────────────────────────────

    def _ingest_single(self, event: MatchEvent, metadata: MatchMetadata) -> None:
        """Write a single event to both stores and update score state."""
        # Update running score
        if event.event_type == EventType.GOAL:
            if event.team == metadata.home_team.name:
                self._score["home"] += 1
            elif event.team == metadata.away_team.name:
                self._score["away"] += 1

        # SQLite
        self.event_store.insert_event(event)

        # Chroma
        self.vector_store.index_event(event, metadata, dict(self._score))

        self._events_ingested += 1
