"""Analyst brief workflow — multi-step agentic pipeline.

This is the showcase "agentic" workflow that demonstrates a production AI
pattern: gather context from multiple sources, synthesise a structured brief,
then verify every claim against the source data before returning.

Flow:
  1. Retrieve match events (full timeline)
  2. Get key player impact stats (top contributors)
  3. Identify tactical turning points (semantic search)
  4. Generate a structured analyst brief
  5. Claim verification — check each claim is supported by evidence
  6. Return verified brief with confidence scores

This runs as a function (not a subgraph) — called by the analyst_brief node.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from graph.tools.registry import get_event_store, get_vector_store
from models.analysis import Confidence, EvidenceItem, StructuredAnalysis


# ── Claim verification model ──────────────────────────────────────


class ClaimVerification(BaseModel):
    """Result of verifying a single claim against source data."""

    claim: str = Field(description="The claim being verified")
    supported: bool = Field(description="Whether the claim is supported by the evidence")
    supporting_evidence: Optional[str] = Field(
        default=None,
        description="The specific evidence that supports or contradicts this claim",
    )


class VerifiedBrief(BaseModel):
    """A verified analyst brief with claim-level support checks."""

    sections: list[BriefSection] = Field(description="Sections of the analyst brief")
    claim_verifications: list[ClaimVerification] = Field(
        description="Verification results for each factual claim"
    )
    overall_confidence: str = Field(
        description="Overall confidence: high, medium, or low"
    )
    verified_claims: int = Field(description="Number of claims that passed verification")
    total_claims: int = Field(description="Total number of claims checked")


class BriefSection(BaseModel):
    """A section of the analyst brief."""

    heading: str = Field(description="Section heading")
    content: str = Field(description="Section content with specific evidence")


# Fix forward reference
VerifiedBrief.model_rebuild()


# ── LLM instances ─────────────────────────────────────────────────

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


# ── Step functions ─────────────────────────────────────────────────


def _step1_gather_match_events(match_id: str) -> str:
    """Step 1: Get the full match timeline."""
    print("  [Brief Step 1] Gathering match events...")
    store = get_event_store()
    events = store.get_all_events(match_id)
    if not events:
        return "No events found."

    lines = [f"Full match timeline ({len(events)} events):"]
    for e in events:
        player = f" - {e.player_name}" if e.player_name else ""
        team = f" ({e.team})" if e.team else ""
        etype = e.event_type.value.replace("_", " ").title()
        lines.append(f"  {e.minute}' [{etype}]{player}{team}: {e.narrative_text}")
    return "\n".join(lines)


def _step2_get_player_impacts(match_id: str) -> str:
    """Step 2: Get stats for the most active players."""
    print("  [Brief Step 2] Gathering player impact stats...")
    store = get_event_store()
    events = store.get_all_events(match_id)

    # Find players with the most events
    player_counts: dict[str, int] = {}
    for e in events:
        if e.player_name:
            player_counts[e.player_name] = player_counts.get(e.player_name, 0) + 1

    # Top 5 most active players
    top_players = sorted(player_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    lines = ["Key player stats:"]
    for player_name, _ in top_players:
        stats = store.get_player_stats(match_id, player_name)
        lines.append(f"\n  {stats['player_name']} ({stats.get('team', 'N/A')}):")
        lines.append(f"    Goals: {stats['goals']}, Assists: {stats['assists']}, "
                      f"Shots: {stats['shots']}, xG: {stats['xg_total']}")
        if stats.get("key_events"):
            for ke in stats["key_events"]:
                lines.append(f"    {ke['minute']}' [{ke['type']}]: {ke['narrative']}")
    return "\n".join(lines)


def _step3_identify_tactical_shifts(match_id: str) -> str:
    """Step 3: Semantic search for tactical turning points."""
    print("  [Brief Step 3] Identifying tactical turning points...")
    vs = get_vector_store()

    queries = [
        "tactical shift formation change",
        "turning point momentum shift",
        "substitution impact",
        "red card sending off consequences",
    ]

    all_docs = []
    seen_ids = set()
    for query in queries:
        docs = vs.search(query, match_id=match_id, k=3)
        for doc in docs:
            eid = doc.metadata.get("event_id")
            if eid not in seen_ids:
                seen_ids.add(eid)
                all_docs.append(doc)

    # Sort by minute
    all_docs.sort(key=lambda d: d.metadata.get("minute", 0))

    lines = [f"Tactical turning points ({len(all_docs)} events):"]
    for doc in all_docs:
        m = doc.metadata
        lines.append(f"  {m.get('minute', '?')}' [{m.get('event_type', '?')}]: {doc.page_content[:200]}")
    return "\n".join(lines)


def _step4_generate_brief(question: str, context: str) -> StructuredAnalysis:
    """Step 4: Generate the structured analyst brief."""
    print("  [Brief Step 4] Generating analyst brief...")

    brief_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a senior football analyst writing a post-match analyst brief.\n\n"
            "Structure your brief with these sections:\n"
            "1. Match Overview — score, key stats, overall narrative\n"
            "2. Tactical Analysis — formations, shape changes, how the game evolved\n"
            "3. Key Moments — the 3-4 events that decided the match\n"
            "4. Player Impact — who made the difference and why\n"
            "5. Talking Points — what pundits would debate\n\n"
            "Rules:\n"
            "- Every claim must reference a specific minute and player\n"
            "- Include 4-8 evidence items covering the most important moments\n"
            "- Set confidence based on how well the evidence supports your analysis\n"
            "- List all data sources used",
        ),
        (
            "human",
            "Question: {question}\n\n"
            "Full match data:\n{context}\n\n"
            "Generate your analyst brief:",
        ),
    ])

    structured_llm = llm.with_structured_output(StructuredAnalysis)
    chain = brief_prompt | structured_llm

    return chain.invoke({"question": question, "context": context})


def _step5_verify_claims(brief: StructuredAnalysis, context: str) -> list[ClaimVerification]:
    """Step 5: Verify each factual claim in the brief against source data.

    This is the key "production AI" step — every claim is checked for support.
    """
    print("  [Brief Step 5] Verifying claims against source data...")

    # Extract claims from the answer
    claim_extraction_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Extract all factual claims from this sports analysis. "
            "A factual claim is any statement about a specific event, player, minute, "
            "statistic, or tactical decision. Return 4-8 key claims.",
        ),
        ("human", "{text}"),
    ])

    class ClaimList(BaseModel):
        claims: list[str] = Field(description="List of factual claims extracted from the text")

    claim_chain = claim_extraction_prompt | llm.with_structured_output(ClaimList)
    extracted = claim_chain.invoke({"text": brief.answer})

    # Verify each claim
    verify_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a fact-checker for sports analysis. Given a claim and the source "
            "match data, determine if the claim is supported.\n\n"
            "A claim is 'supported' if the source data contains evidence that directly "
            "or strongly implies the claim is true.\n"
            "A claim is 'not supported' if there is no evidence, or the evidence contradicts it.",
        ),
        (
            "human",
            "Claim: {claim}\n\nSource data:\n{context}\n\nIs this claim supported?",
        ),
    ])

    verify_chain = verify_prompt | llm.with_structured_output(ClaimVerification)

    verifications = []
    for claim in extracted.claims:
        try:
            v = verify_chain.invoke({"claim": claim, "context": context})
            verifications.append(v)
        except Exception:
            verifications.append(ClaimVerification(
                claim=claim, supported=False, supporting_evidence="Verification failed"
            ))

    return verifications


# ── Main workflow entry point ──────────────────────────────────────


def run_analyst_brief(question: str, match_id: str) -> dict:
    """Execute the full analyst brief workflow.

    Returns a dict with:
    - structured_response: The StructuredAnalysis as a dict
    - generation: Plain text version of the brief
    - claim_verifications: List of claim verification results
    - verified_claims / total_claims: Verification stats
    - workflow_steps: What each step produced (for tracing)
    """
    print("---ANALYST BRIEF WORKFLOW---")

    # Step 1-3: Gather all context
    events_context = _step1_gather_match_events(match_id)
    player_context = _step2_get_player_impacts(match_id)
    tactical_context = _step3_identify_tactical_shifts(match_id)

    # Combine all context
    full_context = "\n\n".join([
        events_context,
        player_context,
        tactical_context,
    ])

    # Step 4: Generate the brief
    brief = _step4_generate_brief(question, full_context)

    # Step 5: Verify claims
    verifications = _step5_verify_claims(brief, full_context)

    verified_count = sum(1 for v in verifications if v.supported)
    total_count = len(verifications)

    # Adjust confidence based on verification results
    if total_count > 0:
        support_ratio = verified_count / total_count
        if support_ratio >= 0.8:
            final_confidence = "high"
        elif support_ratio >= 0.5:
            final_confidence = "medium"
        else:
            final_confidence = "low"
    else:
        final_confidence = brief.confidence.value

    # Build the enhanced structured response
    structured_response = brief.model_dump()
    structured_response["confidence"] = final_confidence
    structured_response["claim_verifications"] = [v.model_dump() for v in verifications]
    structured_response["verified_claims"] = verified_count
    structured_response["total_claims"] = total_count

    # Build plain text generation
    generation = brief.format_plain()
    generation += f"\n\nClaim Verification: {verified_count}/{total_count} claims supported"
    for v in verifications:
        status = "✓" if v.supported else "✗"
        generation += f"\n  {status} {v.claim}"
        if v.supporting_evidence:
            generation += f"\n    → {v.supporting_evidence}"

    print(f"  [Brief Complete] {verified_count}/{total_count} claims verified")

    return {
        "structured_response": structured_response,
        "generation": generation,
        "sources": [
            {"type": "tool_result", "tool": "match_timeline", "args": {"match_id": match_id}},
            {"type": "tool_result", "tool": "player_stats", "args": {"match_id": match_id}},
            {"type": "tool_result", "tool": "tactical_search", "args": {"match_id": match_id}},
        ],
        "workflow_steps": {
            "events_gathered": len(events_context.split("\n")),
            "players_analysed": player_context.count("\n  ") if player_context else 0,
            "tactical_events": len(tactical_context.split("\n")) - 1,
            "claims_verified": verified_count,
            "claims_total": total_count,
        },
    }
