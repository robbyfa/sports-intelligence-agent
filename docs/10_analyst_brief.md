# 10 — Analyst Brief Workflow (`graph/workflows/analyst_brief.py`)

This is the showcase "agentic" feature — a multi-step pipeline that autonomously gathers context, generates analysis, and verifies its own claims.

## When It Triggers

The router detects comprehensive analysis requests:
- "Generate a post-match analyst brief"
- "Write a comprehensive match analysis"
- "Give me a full tactical breakdown"

These get routed to the `analyst_brief` node, which calls `run_analyst_brief()`.

## The 5 Steps

### Step 1: Gather Match Events
Pulls the full match timeline from SQLite via `EventStore.get_all_events()`. This gives the workflow complete event-level context.

### Step 2: Get Player Impact Stats
Identifies the 5 most active players (by event count) and fetches their aggregated stats from SQLite: goals, assists, shots, xG, cards, fouls, key moments.

### Step 3: Identify Tactical Turning Points
Runs 4 semantic searches over Chroma for different tactical themes:
- "tactical shift formation change"
- "turning point momentum shift"
- "substitution impact"
- "red card sending off consequences"

Deduplicates results by event_id and sorts by minute.

### Step 4: Generate Structured Brief
Passes all gathered context (events + stats + tactical analysis) to the LLM with a structured output prompt. The LLM produces a `StructuredAnalysis` with sections covering:
1. Match Overview
2. Tactical Analysis
3. Key Moments
4. Player Impact
5. Talking Points

### Step 5: Claim Verification
This is the production AI pattern:
1. **Extract claims** — an LLM call extracts 4-8 factual claims from the generated brief
2. **Verify each claim** — each claim is independently checked against the source data
3. **Adjust confidence** — the final confidence score is based on the verification pass rate (≥80% → high, ≥50% → medium, <50% → low)

## Why It Skips the Quality Loop

The analyst brief node sets `retries: 99`, which makes the quality loop's `grade_generation` function immediately return "useful" (since `retries >= MAX_RETRIES`). The brief has its own verification (Step 5), so the generic hallucination/answer grading would be redundant.

The graph wires `analyst_brief → END` as a direct edge for the same reason.

## Output

The workflow returns a dict with:
- `structured_response` — the StructuredAnalysis plus `claim_verifications`, `verified_claims`, and `total_claims`
- `generation` — plain text version including the claim verification results
- `sources` — which tools/stores were used
- `workflow_steps` — metadata about what each step produced (event counts, player counts, etc.)
