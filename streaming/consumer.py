"""Event consumer — reads from mock Kafka and yields typed MatchEvent objects."""

from __future__ import annotations

from typing import Generator, Optional

from models.events import MatchEvent
from streaming.mock_kafka import MockConsumer, Message

# Default topic name — matches the producer
SPORTS_EVENTS_TOPIC = "sports_events"


class EventConsumer:
    """Consumes ``MatchEvent`` objects from a mock Kafka topic.

    Wraps ``MockConsumer`` with JSON deserialization back to Pydantic models.

    Args:
        consumer: A ``MockConsumer`` instance.
        topic: Topic name to consume from.
    """

    def __init__(
        self,
        consumer: MockConsumer,
        topic: str = SPORTS_EVENTS_TOPIC,
    ) -> None:
        self._consumer = consumer
        self._topic = topic
        self._consumer.subscribe(topic)

    def poll(self, timeout: float = 1.0) -> Optional[MatchEvent]:
        """Poll for a single event. Returns None if nothing available."""
        msg: Optional[Message] = self._consumer.poll(timeout=timeout)
        if msg is None:
            return None
        return MatchEvent.model_validate_json(msg.value)

    def consume(
        self,
        timeout: float = 1.0,
        max_empty_polls: int = 3,
    ) -> Generator[MatchEvent, None, None]:
        """Yield events until the topic is drained.

        Stops after ``max_empty_polls`` consecutive empty poll results,
        which signals the producer has finished.

        Args:
            timeout: Seconds to wait per poll.
            max_empty_polls: Consecutive empty polls before stopping.

        Yields:
            ``MatchEvent`` objects in the order they were produced.
        """
        empty_count = 0
        while empty_count < max_empty_polls:
            event = self.poll(timeout=timeout)
            if event is None:
                empty_count += 1
                continue
            empty_count = 0
            yield event

    def close(self) -> None:
        """Close the underlying consumer."""
        self._consumer.close()
