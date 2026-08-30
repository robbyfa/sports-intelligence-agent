"""Evaluation dataset — 20 test questions with expected properties.

Each question is tagged with:
- expected_route: which route the router should pick
- expected_keywords: words that MUST appear in a good answer
- expected_players: players that should be mentioned
- expected_minutes: specific minutes that should be referenced
- category: what type of question this is (for grouping eval results)
"""

from __future__ import annotations

EVAL_DATASET: list[dict] = [
    # ── Tool-routed questions (structured queries) ─────────────────
    {
        "id": "q01",
        "question": "What happened between minute 60 and 75?",
        "expected_route": "tools",
        "expected_keywords": ["substitution", "trossard", "akanji"],
        "expected_players": ["Leandro Trossard", "Manuel Akanji"],
        "expected_minutes": [60, 62, 63, 67, 71, 73],
        "category": "timeline",
    },
    {
        "id": "q02",
        "question": "How did Bukayo Saka play?",
        "expected_route": "tools",
        "expected_keywords": ["goal", "penalty"],
        "expected_players": ["Bukayo Saka"],
        "expected_minutes": [76, 90],
        "category": "player_stats",
    },
    {
        "id": "q03",
        "question": "What's the final score and match summary?",
        "expected_route": "tools",
        "expected_keywords": ["2-1", "arsenal", "manchester city"],
        "expected_players": [],
        "expected_minutes": [],
        "category": "match_summary",
    },
    {
        "id": "q04",
        "question": "Show me Haaland's stats for this match.",
        "expected_route": "tools",
        "expected_keywords": ["goal", "shot"],
        "expected_players": ["Erling Haaland"],
        "expected_minutes": [37],
        "category": "player_stats",
    },
    {
        "id": "q05",
        "question": "What substitutions were made in the second half?",
        "expected_route": "tools",
        "expected_keywords": ["substitution"],
        "expected_players": [],
        "expected_minutes": [62, 63, 79, 87],
        "category": "timeline",
    },
    # ── Vectorstore-routed questions (semantic search) ─────────────
    {
        "id": "q06",
        "question": "What was the turning point of the match?",
        "expected_route": "vectorstore",
        "expected_keywords": ["red card", "rodri"],
        "expected_players": ["Rodri"],
        "expected_minutes": [58],
        "category": "narrative",
    },
    {
        "id": "q07",
        "question": "What changed after the red card?",
        "expected_route": "vectorstore",
        "expected_keywords": ["red card", "10 men"],
        "expected_players": ["Rodri"],
        "expected_minutes": [58],
        "category": "narrative",
    },
    {
        "id": "q08",
        "question": "Describe the build-up to the equaliser.",
        "expected_route": "vectorstore",
        "expected_keywords": ["saka", "odegaard"],
        "expected_players": ["Bukayo Saka", "Martin Odegaard"],
        "expected_minutes": [76],
        "category": "narrative",
    },
    {
        "id": "q09",
        "question": "Were there any controversial moments?",
        "expected_route": "vectorstore",
        "expected_keywords": ["var", "penalty", "handball"],
        "expected_players": ["Kyle Walker"],
        "expected_minutes": [88],
        "category": "narrative",
    },
    {
        "id": "q10",
        "question": "What evidence supports that Saka was the best player?",
        "expected_route": "vectorstore",
        "expected_keywords": ["goal", "penalty"],
        "expected_players": ["Bukayo Saka"],
        "expected_minutes": [76, 90],
        "category": "evidence_query",
    },
    {
        "id": "q11",
        "question": "How did City's tactics change after going down to 10 men?",
        "expected_route": "vectorstore",
        "expected_keywords": ["formation", "4-1-4-0"],
        "expected_players": [],
        "expected_minutes": [58, 60],
        "category": "tactical",
    },
    {
        "id": "q12",
        "question": "Which player had the biggest impact on the match?",
        "expected_route": "vectorstore",
        "expected_keywords": [],
        "expected_players": ["Bukayo Saka"],
        "expected_minutes": [],
        "category": "narrative",
    },
    {
        "id": "q13",
        "question": "What are the key talking points from the match?",
        "expected_route": "vectorstore",
        "expected_keywords": ["red card", "comeback", "penalty"],
        "expected_players": [],
        "expected_minutes": [],
        "category": "narrative",
    },
    {
        "id": "q14",
        "question": "How did De Bruyne influence the first half?",
        "expected_route": "vectorstore",
        "expected_keywords": ["assist", "pass"],
        "expected_players": ["Kevin De Bruyne"],
        "expected_minutes": [37],
        "category": "player_narrative",
    },
    # ── Analyst brief questions ────────────────────────────────────
    {
        "id": "q15",
        "question": "Generate a post-match analyst brief.",
        "expected_route": "analyst_brief",
        "expected_keywords": ["arsenal", "city", "2-1"],
        "expected_players": ["Bukayo Saka", "Erling Haaland"],
        "expected_minutes": [37, 58, 76, 90],
        "category": "analyst_brief",
    },
    {
        "id": "q16",
        "question": "Write a comprehensive match analysis.",
        "expected_route": "analyst_brief",
        "expected_keywords": ["tactical", "goal"],
        "expected_players": [],
        "expected_minutes": [],
        "category": "analyst_brief",
    },
    {
        "id": "q17",
        "question": "Give me a full tactical breakdown of this match.",
        "expected_route": "analyst_brief",
        "expected_keywords": ["formation", "tactical"],
        "expected_players": [],
        "expected_minutes": [],
        "category": "analyst_brief",
    },
    # ── Edge case questions ────────────────────────────────────────
    {
        "id": "q18",
        "question": "What happened in the first 10 minutes?",
        "expected_route": "tools",
        "expected_keywords": ["pass", "city"],
        "expected_players": [],
        "expected_minutes": [7, 8],
        "category": "timeline",
    },
    {
        "id": "q19",
        "question": "Did Arsenal deserve to win?",
        "expected_route": "vectorstore",
        "expected_keywords": [],
        "expected_players": [],
        "expected_minutes": [],
        "category": "opinion",
    },
    {
        "id": "q20",
        "question": "Compare the two goalkeepers' performances.",
        "expected_route": "vectorstore",
        "expected_keywords": [],
        "expected_players": ["David Raya", "Ederson"],
        "expected_minutes": [],
        "category": "comparison",
    },
]


def get_dataset() -> list[dict]:
    """Return the full eval dataset."""
    return EVAL_DATASET


def get_by_category(category: str) -> list[dict]:
    """Filter dataset by category."""
    return [q for q in EVAL_DATASET if q["category"] == category]


def get_by_route(route: str) -> list[dict]:
    """Filter dataset by expected route."""
    return [q for q in EVAL_DATASET if q["expected_route"] == route]
