"""Integration tests for the full LangGraph sports intelligence agent.

Runs full graph invocations with fixture data loaded into both stores.
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

from fixtures import load_fixture
from graph.graph import build_graph
from graph.tools import configure
from models.events import MatchFeed
from storage.event_store import EventStore
from storage.vector_store import SportVectorStore
from streaming.pipeline import IngestionPipeline

needs_openai = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)


@pytest.fixture(scope="module")
def agent_setup():
    """Set up stores, ingest fixture, configure tools, build graph."""
    feed = load_fixture("match_001")

    es = EventStore(":memory:")
    vs = SportVectorStore(collection_name="test-graph-integration")

    pipeline = IngestionPipeline(es, vs)
    pipeline.ingest_match(feed)

    configure(event_store=es, vector_store=vs)

    app = build_graph()

    yield app, es, vs

    vs.reset()
    es.close()


def _invoke(app, question: str, match_id: str = "match_001") -> dict:
    """Helper to invoke the graph with standard params."""
    return app.invoke(
        input={
            "question": question,
            "match_id": match_id,
            "retries": 0,
        }
    )


# ── Full graph invocation tests ───────────────────────────────────

@needs_openai
def test_graph_substitution_question(agent_setup):
    app, _, _ = agent_setup
    result = _invoke(app, "What changed after the substitution?")

    assert "generation" in result
    assert len(result["generation"]) > 50
    gen_lower = result["generation"].lower()
    # Should mention substitutions, Trossard, or tactical changes
    assert any(
        word in gen_lower
        for word in ["substitut", "trossard", "akanji", "change", "tactical"]
    )


@needs_openai
def test_graph_match_summary(agent_setup):
    app, _, _ = agent_setup
    result = _invoke(app, "Summarise the match so far.")

    assert "generation" in result
    assert len(result["generation"]) > 50
    gen_lower = result["generation"].lower()
    # Should mention key facts
    assert any(
        word in gen_lower
        for word in ["arsenal", "city", "goal", "2-1", "saka", "haaland"]
    )


@needs_openai
def test_graph_player_impact(agent_setup):
    app, _, _ = agent_setup
    result = _invoke(app, "Which player had the biggest impact?")

    assert "generation" in result
    assert len(result["generation"]) > 50
    # Should mention at least one key player
    gen_lower = result["generation"].lower()
    assert any(
        name in gen_lower
        for name in ["saka", "de bruyne", "haaland", "odegaard", "rodri"]
    )


@needs_openai
def test_graph_red_card_analysis(agent_setup):
    app, _, _ = agent_setup
    result = _invoke(app, "What was the impact of the red card?")

    assert "generation" in result
    gen_lower = result["generation"].lower()
    assert "red card" in gen_lower or "rodri" in gen_lower


@needs_openai
def test_graph_returns_generation_field(agent_setup):
    """Every invocation should produce a non-empty generation."""
    app, _, _ = agent_setup
    result = _invoke(app, "What are the key talking points from this match?")
    assert result.get("generation")
    assert len(result["generation"]) > 20


@needs_openai
def test_graph_structured_response_has_evidence(agent_setup):
    """Structured response should include evidence items."""
    app, _, _ = agent_setup
    result = _invoke(app, "What was the impact of the red card?")

    sr = result.get("structured_response", {})
    assert sr, "Expected structured_response in result"
    assert sr.get("answer"), "Expected answer field"
    assert isinstance(sr.get("evidence", []), list)
    assert len(sr.get("evidence", [])) >= 1, "Expected at least 1 evidence item"


@needs_openai
def test_graph_structured_response_has_confidence(agent_setup):
    """Structured response should include a confidence level."""
    app, _, _ = agent_setup
    result = _invoke(app, "Summarise the match so far.")

    sr = result.get("structured_response", {})
    assert sr.get("confidence") in ("high", "medium", "low"), (
        f"Expected valid confidence, got: {sr.get('confidence')}"
    )


@needs_openai
def test_graph_structured_response_has_sources(agent_setup):
    """Structured response should list data sources used."""
    app, _, _ = agent_setup
    result = _invoke(app, "How did Saka play?")

    sr = result.get("structured_response", {})
    assert isinstance(sr.get("sources", []), list)
    assert len(sr.get("sources", [])) >= 1, "Expected at least 1 source"
