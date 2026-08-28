"""Module-level store registry for tool dependency injection.

Call ``configure()`` once at application startup to set the shared
EventStore and SportVectorStore instances that all tools use.
"""

from __future__ import annotations

from typing import Optional

from storage.event_store import EventStore
from storage.vector_store import SportVectorStore

_event_store: Optional[EventStore] = None
_vector_store: Optional[SportVectorStore] = None


def configure(
    event_store: EventStore,
    vector_store: SportVectorStore,
) -> None:
    """Set the shared store instances for all tools."""
    global _event_store, _vector_store
    _event_store = event_store
    _vector_store = vector_store


def get_event_store() -> EventStore:
    """Get the configured EventStore. Raises if not configured."""
    if _event_store is None:
        raise RuntimeError(
            "Tools not configured. Call graph.tools.configure() first."
        )
    return _event_store


def get_vector_store() -> SportVectorStore:
    """Get the configured SportVectorStore. Raises if not configured."""
    if _vector_store is None:
        raise RuntimeError(
            "Tools not configured. Call graph.tools.configure() first."
        )
    return _vector_store
