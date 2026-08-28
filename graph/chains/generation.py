"""Generation chain — sports analyst prompt with evidence-grounded output."""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a professional sports analyst providing evidence-grounded analysis. "
            "Use the provided match events and context to answer the question. "
            "Always cite specific events by referencing the minute and player involved. "
            "Be concise but insightful — like a pundit giving post-match analysis. "
            "If the context doesn't contain enough information to answer, say so clearly. "
            "Structure longer answers with clear sections when appropriate.",
        ),
        (
            "human",
            "Question: {question}\n\n"
            "Match context and evidence:\n{context}\n\n"
            "Provide your analysis:",
        ),
    ]
)

generation_chain = prompt | llm | StrOutputParser()
