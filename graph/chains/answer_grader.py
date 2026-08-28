"""Answer grader — checks if the generation actually addresses the user's question."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


class GradeAnswer(BaseModel):
    """Binary score for whether the answer addresses the question."""

    binary_score: bool = Field(
        description="Answer addresses the question, 'yes' or 'no'"
    )


structured_llm_grader = llm.with_structured_output(GradeAnswer)

system = """You are a grader assessing whether a sports analysis response adequately
addresses the user's question.

The response should:
- Directly answer what was asked (not just provide tangential information).
- Contain specific evidence or reasoning, not vague generalities.
- Be useful to someone trying to understand the match situation.

Give a binary score: True means the answer resolves the question, False means it does not."""

answer_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        (
            "human",
            "User question: {question}\n\nSports analysis: {generation}",
        ),
    ]
)

answer_grader: RunnableSequence = answer_prompt | structured_llm_grader
