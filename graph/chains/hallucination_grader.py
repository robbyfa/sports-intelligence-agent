"""Hallucination grader — checks if the generation is grounded in the source documents."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


class GradeHallucinations(BaseModel):
    """Binary score for hallucination present in generation answer."""

    binary_score: bool = Field(
        description="Answer is grounded in the facts, 'yes' or 'no'"
    )


structured_llm_grader = llm.with_structured_output(GradeHallucinations)

system = """You are a grader assessing whether a sports analysis response is grounded in
the provided match events and context.

Check that:
- Specific claims about events (goals, cards, substitutions) match the source data.
- Player names and minutes cited are accurate according to the evidence.
- The analysis does not fabricate events or statistics not present in the context.

Give a binary score: True means the answer is grounded in the facts, False means it contains hallucinations."""

hallucination_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        (
            "human",
            "Match events and context:\n\n{documents}\n\nSports analysis:\n{generation}",
        ),
    ]
)

hallucination_grader: RunnableSequence = hallucination_prompt | structured_llm_grader
