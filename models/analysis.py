"""Structured output models for the sports intelligence agent.

Defines the schema for evidence-grounded analysis responses.
The LLM produces this structure directly via structured output,
ensuring every answer comes with evidence, confidence, and sources.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Confidence(str, Enum):
    """How confident the analyst is in the response."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceItem(BaseModel):
    """A single piece of evidence supporting the analysis."""

    minute: int = Field(description="Match minute the evidence refers to")
    description: str = Field(
        description="What happened — e.g. 'quicker winger introduced; attacks became more direct'"
    )
    player: Optional[str] = Field(
        default=None,
        description="Player involved, if applicable",
    )
    event_type: Optional[str] = Field(
        default=None,
        description="Type of event: goal, substitution, red_card, tactical_shift, etc.",
    )


class StructuredAnalysis(BaseModel):
    """The structured output format for every agent response.

    Example output::

        Answer:
        Arsenal became more direct after the 61st-minute substitution.

        Evidence:
        - 61': quicker winger introduced; attacks became more direct down the left
        - 75': winger completed 3 carries, created 1 chance, drew 2 fouls

        Confidence: medium
        Sources: match_events, player_stats
    """

    answer: str = Field(
        description=(
            "The main analytical answer to the question. Be concise but insightful, "
            "like a professional sports pundit. Reference specific minutes and players."
        )
    )
    evidence: list[EvidenceItem] = Field(
        description=(
            "List of specific match events that support the answer. "
            "Each item should reference a specific minute and describe what happened. "
            "Include 2-6 evidence items."
        )
    )
    confidence: Confidence = Field(
        description=(
            "How confident you are in this analysis based on the available evidence. "
            "'high' = strong evidence directly supports the claims. "
            "'medium' = evidence is suggestive but not conclusive. "
            "'low' = limited evidence, answer involves significant inference."
        )
    )
    sources: list[str] = Field(
        description=(
            "Which data sources were used: e.g. 'match_events', 'player_stats', "
            "'match_summary', 'event_search', 'web_search'"
        )
    )

    def format_text(self) -> str:
        """Render the analysis as a readable text block."""
        lines = [self.answer, ""]

        if self.evidence:
            lines.append("**Evidence:**")
            for e in self.evidence:
                player_tag = f" ({e.player})" if e.player else ""
                lines.append(f"- **{e.minute}'**{player_tag}: {e.description}")
            lines.append("")

        lines.append(f"**Confidence:** {self.confidence.value}")
        lines.append(f"**Sources:** {', '.join(self.sources)}")

        return "\n".join(lines)

    def format_plain(self) -> str:
        """Render as plain text (for CLI / grader consumption)."""
        lines = [f"Answer:\n{self.answer}", ""]

        if self.evidence:
            lines.append("Evidence:")
            for e in self.evidence:
                player_tag = f" ({e.player})" if e.player else ""
                lines.append(f"  - {e.minute}'{player_tag}: {e.description}")
            lines.append("")

        lines.append(f"Confidence: {self.confidence.value}")
        lines.append(f"Sources: {', '.join(self.sources)}")

        return "\n".join(lines)
