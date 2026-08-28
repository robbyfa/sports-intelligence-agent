"""Grade documents node — filters out irrelevant documents."""

from __future__ import annotations

from typing import Any, Dict

from graph.chains.retrieval_grader import retrieval_grader
from graph.state import GraphState


def grade_documents(state: GraphState) -> Dict[str, Any]:
    """Grade retrieved documents for relevance to the question.

    If any document is not relevant, sets the web_search flag
    as a fallback option.
    """
    print("---GRADE DOCUMENTS---")
    question = state["question"]
    documents = state["documents"]

    filtered_docs = []
    web_search = False

    for doc in documents:
        score = retrieval_grader.invoke(
            {"question": question, "document": doc.page_content}
        )
        grade = score.binary_score
        if grade.lower() == "yes":
            print("  GRADE: DOCUMENT RELEVANT")
            filtered_docs.append(doc)
        else:
            print("  GRADE: DOCUMENT NOT RELEVANT")
            web_search = True

    return {
        "documents": filtered_docs,
        "question": question,
        "web_search": web_search,
    }
