"""Generation chain — sports analyst prompt with structured, evidence-grounded output."""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from models.analysis import StructuredAnalysis

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ── Structured generation (primary) ───────────────────────────────

structured_llm = llm.with_structured_output(StructuredAnalysis)

structured_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a professional sports analyst providing evidence-grounded analysis.\n\n"
            "Rules:\n"
            "- Base every claim on specific match events from the provided context.\n"
            "- In your answer, reference specific minutes and players.\n"
            "- In evidence items, cite the exact minute and describe what happened.\n"
            "- Set confidence to 'high' when evidence directly supports your claims, "
            "'medium' when evidence is suggestive, 'low' when you're inferring.\n"
            "- List which data sources contributed: 'match_events', 'player_stats', "
            "'match_summary', 'event_search', 'web_search'.\n"
            "- Be concise but insightful — like a pundit giving post-match analysis.\n"
            "- If the context doesn't contain enough information, say so and set confidence to 'low'.",
        ),
        (
            "human",
            "Question: {question}\n\n"
            "Match context and evidence:\n{context}\n\n"
            "Provide your structured analysis:",
        ),
    ]
)

structured_generation_chain = structured_prompt | structured_llm

# ── Plain text generation (for grader compatibility) ──────────────

plain_prompt = ChatPromptTemplate.from_messages(
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

generation_chain = plain_prompt | llm | StrOutputParser()
