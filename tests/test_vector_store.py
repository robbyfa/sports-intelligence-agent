"""Tests for the Chroma-backed sports vector store.

These tests require a valid OPENAI_API_KEY for embedding generation.
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

from fixtures import load_fixture
from models.events import EventType, MatchFeed
from storage.vector_store import SportVectorStore

needs_openai = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)


@pytest.fixture
def feed() -> MatchFeed:
    return load_fixture("match_001")


@pytest.fixture
def vs(feed) -> SportVectorStore:
    """In-memory vector store pre-loaded with the fixture match."""
    store = SportVectorStore(collection_name="test-sports-events")
    store.index_match(feed)
    yield store
    store.reset()


# ── Indexing ───────────────────────────────────────────────────────

@needs_openai
def test_index_match_returns_event_count(feed):
    store = SportVectorStore(collection_name="test-index-count")
    count = store.index_match(feed)
    assert count == len(feed.events)
    store.reset()


@needs_openai
def test_index_single_event(feed):
    store = SportVectorStore(collection_name="test-index-single")
    event = feed.events[0]
    doc_id = store.index_event(event, feed.metadata)
    assert doc_id == event.event_id
    store.reset()


# ── Search ─────────────────────────────────────────────────────────

@needs_openai
def test_search_red_card(vs):
    """Searching for 'red card' should return the Rodri red card event."""
    docs = vs.search("red card sending off", match_id="match_001", k=3)
    assert len(docs) > 0
    # The top result should mention Rodri or red card
    top = docs[0]
    assert "red" in top.page_content.lower() or "rodri" in top.page_content.lower()


@needs_openai
def test_search_substitution_impact(vs):
    """Searching for substitution impact should find substitution events."""
    docs = vs.search("What changed after the substitution?", match_id="match_001", k=5)
    assert len(docs) > 0
    event_types = [d.metadata.get("event_type") for d in docs]
    # Should include at least one substitution or tactical shift
    assert any(
        t in ("substitution", "tactical_shift") for t in event_types
    ), f"Expected substitution-related events, got: {event_types}"


@needs_openai
def test_search_goal_scorer(vs):
    """Searching for Haaland goal should return relevant events."""
    docs = vs.search("Haaland goal", match_id="match_001", k=3)
    assert len(docs) > 0
    top = docs[0]
    assert "haaland" in top.page_content.lower()


@needs_openai
def test_search_with_match_id_filter(vs, feed):
    """match_id filter restricts results correctly."""
    docs = vs.search("goal", match_id="match_001", k=5)
    for doc in docs:
        assert doc.metadata["match_id"] == "match_001"


@needs_openai
def test_search_with_event_type_filter(vs):
    """Additional filters narrow results."""
    docs = vs.search(
        "what happened",
        match_id="match_001",
        filters={"event_type": "goal"},
        k=5,
    )
    for doc in docs:
        assert doc.metadata["event_type"] == "goal"


@needs_openai
def test_search_returns_metadata(vs):
    """Returned documents have expected metadata fields."""
    docs = vs.search("penalty", match_id="match_001", k=3)
    assert len(docs) > 0
    for doc in docs:
        assert "match_id" in doc.metadata
        assert "event_id" in doc.metadata
        assert "minute" in doc.metadata
        assert "event_type" in doc.metadata


# ── Document content quality ───────────────────────────────────────

@needs_openai
def test_document_content_includes_context(vs):
    """Documents should include team names, minute, and narrative."""
    docs = vs.search("goal", match_id="match_001", k=1)
    assert len(docs) > 0
    content = docs[0].page_content
    # Should include team short names and minute marker
    assert "ARS" in content or "MCI" in content
    assert "Minute" in content


@needs_openai
def test_document_content_includes_score(vs):
    """Goal documents should include score context."""
    docs = vs.search(
        "Arsenal equalise",
        match_id="match_001",
        filters={"event_type": "goal"},
        k=3,
    )
    assert len(docs) > 0
    # At least one should have score in content
    has_score = any("Score:" in d.page_content for d in docs)
    assert has_score


# ── Retriever interface ────────────────────────────────────────────

@needs_openai
def test_as_retriever(vs):
    """as_retriever returns a working LangChain retriever."""
    retriever = vs.as_retriever(search_kwargs={"k": 3})
    docs = retriever.invoke("match summary")
    assert len(docs) > 0
    assert all(hasattr(d, "page_content") for d in docs)
