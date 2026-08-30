"""Tool execute node — calls structured tools based on the user's question.

Uses the LLM with bound tools to decide which tool(s) to call,
then collects the results into the graph state.
"""

from __future__ import annotations

from typing import Any, Dict

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from graph.state import GraphState
from graph.tools import get_all_tools


def tool_execute(state: GraphState) -> Dict[str, Any]:
    """Execute structured tools based on the user's question.

    The LLM decides which tool(s) to call. Results are collected
    as context documents for the generation step.
    """
    print("---TOOL EXECUTE---")
    question = state["question"]
    match_id = state.get("match_id", "match_001")

    tools = get_all_tools()
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm_with_tools = llm.bind_tools(tools)

    # Ask the LLM which tools to call
    prompt = (
        f"You are a sports data assistant. The user is asking about match '{match_id}'. "
        f"Use the available tools to gather the information needed to answer this question. "
        f"Always pass match_id='{match_id}' when calling tools.\n\n"
        f"IMPORTANT: If the question is about player impact, best player, or player comparison, "
        f"you MUST call get_match_summary first to see who scored and who was involved in key moments, "
        f"then call get_player_stats for the 2-3 most relevant players to compare their stats. "
        f"Call multiple tools when needed — don't just call one.\n\n"
        f"Question: {question}"
    )

    response = llm_with_tools.invoke([HumanMessage(content=prompt)])

    tool_results = []
    sources = []

    # Execute any tool calls
    if response.tool_calls:
        tool_map = {t.name: t for t in tools}
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            print(f"  Calling tool: {tool_name}({tool_args})")

            if tool_name in tool_map:
                result = tool_map[tool_name].invoke(tool_args)
                tool_results.append(result)
                sources.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "type": "tool_result",
                })

    # If no tools were called, provide a fallback
    if not tool_results:
        print("  No tools called, falling back to text response")
        if response.content:
            tool_results.append(response.content)

    # Convert tool results to document-like strings for the grading step
    from langchain_core.documents import Document

    documents = [Document(page_content=r) for r in tool_results]

    return {
        "documents": documents,
        "tool_results": tool_results,
        "sources": sources,
        "question": question,
    }
