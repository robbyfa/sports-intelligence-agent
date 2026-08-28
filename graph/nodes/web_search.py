"""Web search node — fallback for questions not about the current match."""

from __future__ import annotations

from typing import Any, Dict

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_tavily import TavilySearch

from graph.state import GraphState

load_dotenv()

web_search_tool = TavilySearch(max_results=3)


def web_search(state: GraphState) -> Dict[str, Any]:
    """Perform a web search as a fallback for out-of-match questions."""
    print("---WEB SEARCH---")
    question = state["question"]
    documents = state.get("documents") or []

    tavily_results = web_search_tool.invoke({"query": question})
    joined = "\n".join(r["content"] for r in tavily_results)

    web_results = Document(page_content=joined)
    documents.append(web_results)

    return {"documents": documents, "question": question}
