"""LangGraph agent for streaming sports intelligence.

Flow:
  route_question → (tool_execute | event_search | websearch)
    → grade_documents → generate
    → hallucination_check → answer_check
    → END (with sources) or retry

The graph is compiled into ``app`` for use by main.py and the Streamlit UI.
"""

from __future__ import annotations

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

from graph.chains.answer_grader import answer_grader
from graph.chains.hallucination_grader import hallucination_grader
from graph.chains.router import RouteQuery, question_router
from graph.consts import (
    EVENT_SEARCH,
    GENERATE,
    GRADE_DOCUMENTS,
    TOOL_EXECUTE,
    WEBSEARCH,
)
from graph.nodes import (
    event_search,
    generate,
    grade_documents,
    tool_execute,
    web_search,
)
from graph.state import GraphState

load_dotenv()

MAX_RETRIES = 3


# ── Routing functions ──────────────────────────────────────────────


def route_question(state: GraphState) -> str:
    """Route the question to the appropriate data source."""
    print("---ROUTE QUESTION---")
    question = state["question"]
    source: RouteQuery = question_router.invoke({"question": question})

    if source.datasource == "tools":
        print("  → ROUTE TO TOOLS")
        return TOOL_EXECUTE
    elif source.datasource == "vectorstore":
        print("  → ROUTE TO EVENT SEARCH")
        return EVENT_SEARCH
    elif source.datasource == WEBSEARCH:
        print("  → ROUTE TO WEB SEARCH")
        return WEBSEARCH
    else:
        print("  → DEFAULT TO EVENT SEARCH")
        return EVENT_SEARCH


def decide_to_generate(state: GraphState) -> str:
    """After grading, decide whether to generate or fall back to web search."""
    print("---ASSESS GRADED DOCUMENTS---")
    documents = state.get("documents", [])
    web_search_flag = state.get("web_search", False)

    if not documents and web_search_flag:
        print("  → NO RELEVANT DOCS, FALLING BACK TO WEB SEARCH")
        return WEBSEARCH
    else:
        print("  → GENERATE")
        return GENERATE


def grade_generation(state: GraphState) -> str:
    """Check the generation for hallucinations and answer quality.

    Returns "useful", "not useful", or "not supported".
    Respects the retry limit to prevent infinite loops.
    """
    print("---CHECK GENERATION QUALITY---")
    question = state["question"]
    documents = state["documents"]
    generation = state["generation"]
    retries = state.get("retries", 0)

    # If we've hit max retries, accept what we have
    if retries >= MAX_RETRIES:
        print("  → MAX RETRIES REACHED, ACCEPTING GENERATION")
        return "useful"

    # Check hallucinations
    score = hallucination_grader.invoke(
        {"documents": documents, "generation": generation}
    )
    if not score.binary_score:
        print("  → GENERATION NOT GROUNDED, RE-TRY")
        return "not supported"

    print("  → GENERATION IS GROUNDED")

    # Check if it addresses the question
    score = answer_grader.invoke(
        {"question": question, "generation": generation}
    )
    if score.binary_score:
        print("  → GENERATION ADDRESSES QUESTION")
        return "useful"
    else:
        print("  → GENERATION DOES NOT ADDRESS QUESTION")
        return "not useful"


# ── Build the graph ────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """Build and return the compiled sports intelligence graph."""
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node(TOOL_EXECUTE, tool_execute)
    workflow.add_node(EVENT_SEARCH, event_search)
    workflow.add_node(GRADE_DOCUMENTS, grade_documents)
    workflow.add_node(GENERATE, generate)
    workflow.add_node(WEBSEARCH, web_search)

    # Entry point: route the question
    workflow.set_conditional_entry_point(
        route_question,
        {
            TOOL_EXECUTE: TOOL_EXECUTE,
            EVENT_SEARCH: EVENT_SEARCH,
            WEBSEARCH: WEBSEARCH,
        },
    )

    # After tool execution or event search → grade documents
    workflow.add_edge(TOOL_EXECUTE, GRADE_DOCUMENTS)
    workflow.add_edge(EVENT_SEARCH, GRADE_DOCUMENTS)

    # After grading → generate or fall back to web search
    workflow.add_conditional_edges(
        GRADE_DOCUMENTS,
        decide_to_generate,
        {
            WEBSEARCH: WEBSEARCH,
            GENERATE: GENERATE,
        },
    )

    # Web search → generate
    workflow.add_edge(WEBSEARCH, GENERATE)

    # After generation → quality check
    workflow.add_conditional_edges(
        GENERATE,
        grade_generation,
        {
            "not supported": GENERATE,  # Re-generate (hallucination)
            "not useful": EVENT_SEARCH,  # Try different context
            "useful": END,
        },
    )

    return workflow.compile()


# Compile the default app instance
app = build_graph()
