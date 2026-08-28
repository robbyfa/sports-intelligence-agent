"""Match event producer — publishes events to the mock Kafka topic.

Supports two modes:
- **batch**: all events pushed immediately (for testing / quick demos)
- **realtime**: events drip in with delays proportional to minute gaps,
  controlled by a speed multiplier (for live-style demos)
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from models.events import MatchEvent, MatchFeed
from streaming.mock_kafka import MockProducer

# Default topic name — matches the architecture spec
SPORTS_EVENTS_TOPIC = "sports_events"


class MatchEventProducer:
    """Publishes ``MatchEvent`` objects to a mock Kafka topic.

    Args:
        producer: A ``MockProducer`` instance.
        topic: Topic name to publish to.
    """

    def __init__(
        self,
        producer: MockProducer,
        topic: str = SPORTS_EVENTS_TOPIC,
    ) -> None:
        self._producer = producer
        self._topic = topic

    def produce_batch(
        self,
        feed: MatchFeed,
        on_event: Optional[Callable[[MatchEvent], None]] = None,
    ) -> int:
        """Push all events from a match feed at once.

        Args:
            feed: The complete match feed.
            on_event: Optional callback invoked after each event is produced.

        Returns:
            Number of events produced.
        """
        events = feed.events_by_minute()
        for event in events:
            self._publish(event)
            if on_event:
                on_event(event)
        self._producer.flush()
        return len(events)

    def produce_realtime(
        self,
        feed: MatchFeed,
        speed_multiplier: float = 1.0,
        on_event: Optional[Callable[[MatchEvent], None]] = None,
    ) -> int:
        """Push events with realistic delays based on match time.

        Each gap between events (in match minutes) is converted to a real
        delay: ``gap_seconds / speed_multiplier``.  A ``speed_multiplier``
        of 10.0 means a 5-minute gap in match time becomes 30 real seconds.

        Args:
            feed: The complete match feed.
            speed_multiplier: How much faster than real-time (default 1.0 = real-time,
                              10.0 = 10x speed, etc.).
            on_event: Optional callback invoked after each event is produced.

        Returns:
            Number of events produced.
        """
        if speed_multiplier <= 0:
            raise ValueError("speed_multiplier must be positive")

        events = feed.events_by_minute()
        prev_match_seconds = 0.0

        for event in events:
            current_match_seconds = event.minute * 60 + event.second
            gap = current_match_seconds - prev_match_seconds

            if gap > 0:
                real_delay = gap / speed_multiplier
                time.sleep(real_delay)

            self._publish(event)
            if on_event:
                on_event(event)
            prev_match_seconds = current_match_seconds

        self._producer.flush()
        return len(events)

    def _publish(self, event: MatchEvent) -> None:
        """Serialize and produce a single event."""
        self._producer.produce(
            topic=self._topic,
            value=event.model_dump_json(),
            key=event.match_id,
        )
