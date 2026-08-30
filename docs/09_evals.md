# 09 — Evaluation Framework (`evals/`)

The eval framework lets you measure how well the agent performs across multiple dimensions without manual inspection.

## Dataset (`evals/dataset.py`)

20 test questions, each tagged with:

- `expected_route` — which route the router should pick (tools / vectorstore / analyst_brief / websearch)
- `expected_keywords` — words that should appear in a good answer
- `expected_players` — player names that should be mentioned
- `expected_minutes` — specific match minutes that should be referenced
- `category` — for grouping results (timeline, player_stats, narrative, tactical, analyst_brief, etc.)

## Evaluators (`evals/evaluators.py`)

Five evaluation dimensions:

| Dimension | How it works |
|-----------|-------------|
| **Retrieval relevance** | LLM judge scores whether retrieved documents are relevant to the question (0-1) |
| **Groundedness** | LLM judge checks if the answer's factual claims are supported by the context (0-1) |
| **Citation quality** | Regex checks for minute references + keyword/player matching against expected values |
| **Tool selection** | Compares the actual route taken vs the expected route |
| **Event freshness** | Checks if key match minutes appear in the answer text |

The overall score is a weighted average: groundedness (30%), retrieval relevance (20%), citation quality (20%), tool selection (15%), event freshness (15%).

## Runner (`evals/run_evals.py`)

```bash
python -m evals.run_evals                    # all 20 questions
python -m evals.run_evals --category narrative  # filter by category
python -m evals.run_evals --question q06        # single question
python -m evals.run_evals --output results.json # save to JSON
```

The runner prints per-question scores, aggregate averages, and a category breakdown table.

## LangSmith Integration

When `LANGCHAIN_API_KEY` is set, every eval run is automatically traced in LangSmith under the `sports-intelligence-evals` project. This gives you full visibility into each LLM call, tool invocation, and grading decision.
