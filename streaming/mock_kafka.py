"""In-process mock Kafka using Python queues.

Simulates a Kafka broker with topics backed by ``queue.Queue``.
Drop-in replacement for local development — swap for ``confluent_kafka``
when moving to a real broker.

Usage::

    registry = TopicRegistry()
    producer = MockProducer(registry)
    consumer = MockConsumer(registry)

    producer.produce("sports_events", value=b'{"event_id": "1"}')
    consumer.subscribe("sports_events")
    msg = consumer.poll(timeout=1.0)
"""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Message:
    """A single message on a topic, mirroring Kafka's message structure."""

    topic: str
    value: bytes
    key: Optional[bytes] = None
    timestamp: float = field(default_factory=time.time)
    offset: int = 0

    def value_json(self) -> dict:
        """Deserialize the value as JSON."""
        return json.loads(self.value)


class TopicRegistry:
    """Shared registry of topics backed by ``queue.Queue`` instances.

    Thread-safe. One registry is shared between producers and consumers
    within the same process.
    """

    def __init__(self) -> None:
        self._topics: dict[str, queue.Queue[Message]] = {}
        self._offsets: dict[str, int] = {}
        self._lock = threading.Lock()

    def get_or_create(self, topic: str) -> queue.Queue[Message]:
        with self._lock:
            if topic not in self._topics:
                self._topics[topic] = queue.Queue()
                self._offsets[topic] = 0
            return self._topics[topic]

    def next_offset(self, topic: str) -> int:
        with self._lock:
            offset = self._offsets.get(topic, 0)
            self._offsets[topic] = offset + 1
            return offset

    def reset(self) -> None:
        """Clear all topics. Useful between tests."""
        with self._lock:
            self._topics.clear()
            self._offsets.clear()


class MockProducer:
    """Produces messages to in-process topic queues.

    Mirrors the essential surface of ``confluent_kafka.Producer``.
    """

    def __init__(self, registry: TopicRegistry) -> None:
        self._registry = registry

    def produce(
        self,
        topic: str,
        value: bytes | str | dict,
        key: Optional[bytes | str] = None,
    ) -> None:
        """Serialize and push a message to the topic queue."""
        if isinstance(value, dict):
            value = json.dumps(value).encode("utf-8")
        elif isinstance(value, str):
            value = value.encode("utf-8")

        if isinstance(key, str):
            key = key.encode("utf-8")

        q = self._registry.get_or_create(topic)
        offset = self._registry.next_offset(topic)

        msg = Message(topic=topic, value=value, key=key, offset=offset)
        q.put(msg)

    def flush(self, timeout: float = 5.0) -> None:
        """No-op for mock — all produces are synchronous."""
        pass


class MockConsumer:
    """Consumes messages from in-process topic queues.

    Mirrors the essential surface of ``confluent_kafka.Consumer``.
    """

    def __init__(self, registry: TopicRegistry) -> None:
        self._registry = registry
        self._subscribed_topic: Optional[str] = None
        self._queue: Optional[queue.Queue[Message]] = None

    def subscribe(self, topic: str) -> None:
        """Subscribe to a topic (one topic at a time for simplicity)."""
        self._subscribed_topic = topic
        self._queue = self._registry.get_or_create(topic)

    def poll(self, timeout: float = 1.0) -> Optional[Message]:
        """Poll for the next message, blocking up to *timeout* seconds.

        Returns ``None`` if no message is available within the timeout.
        """
        if self._queue is None:
            raise RuntimeError("Consumer not subscribed to any topic")
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self) -> None:
        """Unsubscribe and clean up."""
        self._subscribed_topic = None
        self._queue = None
