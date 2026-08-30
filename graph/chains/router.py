"""Question router — decides whether to use tools, semantic search, analyst brief, or web search."""

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class RouteQuery(BaseModel):
    """Route a user question to the most relevant data source."""

    datasource: Literal["tools", "vectorstore", "analyst_brief", "websearch"] = Field(
        ...,
        description=(
            "Given a user question about a sports match, choose the best data source. "
            "Use 'tools' for specific queries about timelines, player stats, or match summaries. "
            "Use 'vectorstore' for semantic questions about events, narratives, and analysis. "
            "Use 'analyst_brief' for comprehensive analysis requests that need multiple data sources. "
            "Use 'websearch' only if the question is not about the current match data."
        ),
    )


llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
structured_llm_router = llm.with_structured_output(RouteQuery)

system = """You are an expert at routing sports analysis questions to the right data source.

You have four options:

- **analyst_brief**: Use for comprehensive analysis requests that need a multi-step workflow.
  These are questions that require gathering match events, player stats, AND tactical context.
  Examples:
  - "Generate a post-match analyst brief" → analyst_brief
  - "Give me a full match analysis" → analyst_brief
  - "Write a match report" → analyst_brief
  - "What's the complete tactical breakdown?" → analyst_brief
  - "Produce a pundit-style analysis of the match" → analyst_brief

- **tools**: Use for queries that need structured data: timelines, player stats, match summaries,
  or comparisons that depend on statistics. IMPORTANT: any question about player performance,
  impact, or comparisons should use tools because it needs aggregated stats (goals, assists,
  shots, xG) to give an accurate answer.
  Examples:
  - "What happened between minute 60 and 75?" → tools (timeline query)
  - "How did Saka play?" → tools (player stats)
  - "Player stats for Haaland" → tools (player stats)
  - "Which player had the biggest impact?" → tools (needs stats for multiple players)
  - "Who was the best player?" → tools (needs stats comparison)
  - "Compare the two strikers" → tools (player stats)
  - "What's the score?" or "Summarise the match" → tools (match summary)
  - "Show me the substitutions" → tools (timeline or summary)
  - "How many shots did Arsenal have?" → tools (match summary)
  
- **vectorstore**: Use for semantic or narrative questions about specific moments, build-up play,
  or context that requires understanding the flow of the game.
  Examples:
  - "What was the turning point?" → vectorstore
  - "Describe the build-up to the equaliser" → vectorstore
  - "What changed after the red card?" → vectorstore
  - "Were there any controversial moments?" → vectorstore
  - "What are the key talking points?" → vectorstore
  
- **websearch**: Use only when the question is clearly not about the current match data.
  Examples:
  - "What is the offside rule?" → websearch
  - "Who won the Champions League last year?" → websearch

Choose analyst_brief when the question asks for a comprehensive, multi-faceted analysis.
Choose tools when the answer depends on statistics, numbers, or player comparisons.
Choose vectorstore when the answer depends on narrative context or the flow of the game.
"""

route_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        ("human", "{question}"),
    ]
)

question_router = route_prompt | structured_llm_router
