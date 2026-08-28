"""Tests for the sports intelligence chains.

These tests verify the router, graders, and generation chain work
correctly in a sports context.
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

from graph.chains.retrieval_grader import GradeDocuments, retrieval_grader
from graph.chains.generation import generation_chain
from graph.chains.router import RouteQuery, question_router
from graph.chains.hallucination_grader import GradeHallucinations, hallucination_grader
from graph.chains.answer_grader import GradeAnswer, answer_grader

needs_openai = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)

# Sample sports context for testing
SAMPLE_EVENT_DOC = (
    "[ARS vs MCI] [Minute 76'] [Score: ARS 1 - 1 MCI] "
    "[Bukayo Saka (Arsenal)] [Goal] "
    "GOAL! Arsenal equalise! Odegaard plays a sublime reverse pass to Saka "
    "on the right side of the box. Saka takes a touch and fires across Ederson "
    "into the far corner. The Emirates erupts! Arsenal 1-1 Manchester City."
)

SAMPLE_CONTEXT = (
    "Timeline: Minute 55' to 80'\n"
    "55' [Shot] - Gabriel Martinelli (Arsenal): Martinelli cuts in and unleashes a drive. Saved.\n"
    "58' [Red Card] - Rodri (Manchester City): RED CARD! Second yellow for late challenge on Saka.\n"
    "60' [Tactical Shift] - Manchester City: Switch to 4-1-4-0 after red card.\n"
    "62' [Substitution] - Manchester City: Grealish OFF, Akanji ON.\n"
    "63' [Substitution] - Arsenal: Zinchenko OFF, Trossard ON.\n"
    "76' [Goal] - Bukayo Saka (Arsenal): Arsenal equalise via Odegaard reverse pass.\n"
)


# ── Router ─────────────────────────────────────────────────────────

@needs_openai
def test_router_to_tools_for_timeline():
    res: RouteQuery = question_router.invoke(
        {"question": "What happened between minute 60 and 75?"}
    )
    assert res.datasource == "tools"


@needs_openai
def test_router_to_tools_for_player_stats():
    res: RouteQuery = question_router.invoke(
        {"question": "How did Saka play? Show me his stats."}
    )
    assert res.datasource == "tools"


@needs_openai
def test_router_to_tools_for_match_summary():
    res: RouteQuery = question_router.invoke(
        {"question": "What's the current score and match summary?"}
    )
    assert res.datasource == "tools"


@needs_openai
def test_router_to_vectorstore_for_narrative():
    res: RouteQuery = question_router.invoke(
        {"question": "What was the turning point of the match?"}
    )
    assert res.datasource == "vectorstore"


@needs_openai
def test_router_to_websearch_for_general():
    res: RouteQuery = question_router.invoke(
        {"question": "What is the offside rule in football?"}
    )
    assert res.datasource == "websearch"


# ── Retrieval grader ───────────────────────────────────────────────

@needs_openai
def test_retrieval_grader_relevant():
    res: GradeDocuments = retrieval_grader.invoke(
        {"question": "Who scored for Arsenal?", "document": SAMPLE_EVENT_DOC}
    )
    assert res.binary_score.lower() == "yes"


@needs_openai
def test_retrieval_grader_not_relevant():
    res: GradeDocuments = retrieval_grader.invoke(
        {
            "question": "What is the offside rule?",
            "document": SAMPLE_EVENT_DOC,
        }
    )
    assert res.binary_score.lower() == "no"


# ── Generation ─────────────────────────────────────────────────────

@needs_openai
def test_generation_chain_produces_output():
    generation = generation_chain.invoke(
        {"question": "What happened after the red card?", "context": SAMPLE_CONTEXT}
    )
    assert len(generation) > 0
    # Should reference the red card or its aftermath
    gen_lower = generation.lower()
    assert "red card" in gen_lower or "rodri" in gen_lower or "substitution" in gen_lower


# ── Hallucination grader ───────────────────────────────────────────

@needs_openai
def test_hallucination_grader_grounded():
    generation = (
        "After Rodri's red card in the 58th minute, Arsenal capitalised. "
        "Saka equalised in the 76th minute with help from an Odegaard reverse pass."
    )
    res: GradeHallucinations = hallucination_grader.invoke(
        {"documents": SAMPLE_CONTEXT, "generation": generation}
    )
    assert res.binary_score is True


@needs_openai
def test_hallucination_grader_not_grounded():
    generation = (
        "Haaland scored a hat-trick in the second half to seal the victory for City."
    )
    res: GradeHallucinations = hallucination_grader.invoke(
        {"documents": SAMPLE_CONTEXT, "generation": generation}
    )
    assert res.binary_score is False


# ── Answer grader ──────────────────────────────────────────────────

@needs_openai
def test_answer_grader_addresses_question():
    generation = (
        "The red card to Rodri at 58' was the turning point. Arsenal brought on "
        "Trossard and dominated, leading to Saka's equaliser at 76'."
    )
    res: GradeAnswer = answer_grader.invoke(
        {"question": "What changed after the red card?", "generation": generation}
    )
    assert res.binary_score is True


@needs_openai
def test_answer_grader_does_not_address():
    generation = "The weather in London was pleasant that evening."
    res: GradeAnswer = answer_grader.invoke(
        {"question": "What changed after the red card?", "generation": generation}
    )
    assert res.binary_score is False
