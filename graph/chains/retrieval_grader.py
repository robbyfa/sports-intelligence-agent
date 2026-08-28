"""Retrieval grader — assesses relevance of retrieved documents to the sports question."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


class GradeDocuments(BaseModel):
    """Binary score for relevance check on retrieved documents."""

    binary_score: str = Field(
        description="Documents are relevant to the question, 'yes' or 'no'"
    )


structured_llm_grader = llm.with_structured_output(GradeDocuments)

system = """You are a grader assessing the relevance of a retrieved sports event document 
to a user's question about a match.

The document may contain match event narratives, player actions, tactical information,
or match statistics. If the document contains information that could help answer the
question — even partially — grade it as relevant.

Give a binary score 'yes' or 'no' to indicate whether the document is relevant."""

grade_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        (
            "human",
            "Retrieved document:\n\n{document}\n\nUser question: {question}",
        ),
    ]
)

retrieval_grader = grade_prompt | structured_llm_grader
