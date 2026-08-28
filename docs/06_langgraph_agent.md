# 06 — LangGraph Agent (`graph/`)

This is the brain of the system. A LangGraph `StateGraph` that routes questions, retrieves context, generates answers, and checks quality.

## State (`graph/state.py`)

The graph passes a `GraphState` TypedDict between nodes:

| Field | Type | Purpose |
|-------|------|---------|
| `question` | `str` | The user's question |
| `match_id` | `str` | Which match to query |
| `generation` | `str` | The LLM's answer |
| `web_search` | `bool` | Flag to fall back to web search |
| `documents` | `list` | Retrieved context documents |
| `tool_results` | `list[str]` | Raw string results from tool calls |
| `sources` | `list[dict]` | Evidence attribution for the UI |
| `retries` | `int` | Counter to prevent infinite loops |

## The Graph Flow

```
User Question
     |
  [route_question]
     |
     +-- "tools"       --> [tool_execute]   --> [grade_documents]
     +-- "vectorstore"  --> [event_search]   --> [grade_documents]
     +-- "websearch"    --> [web_search]     --> [generate]
                                                    |
                            [grade_documents] ------+
                                 |
                                 +-- documents OK  --> [generate]
                                 +-- no good docs  --> [web_search] --> [generate]
                                                                          |
                                                      [grade_generation] -+
                                                           |
                                                           +-- "useful"         --> END
                                                           +-- "not supported"  --> [generate] (retry)
                                                           +-- "not useful"     --> [event_search] (try different context)
```

## Chains (`graph/chains/`)

Each chain is a LangChain `prompt | llm` pipeline. They're pure functions — no side effects, easy to test independently.

### `router.py` — Question Router

Uses `gpt-4o-mini` with structured output to classify the question into one of three routes:
- `"tools"` — for specific queries (timeline, stats, summary)
- `"vectorstore"` — for semantic/narrative questions
- `"websearch"` — for questions unrelated to the match data

The system prompt includes examples of each category to guide the LLM.

### `generation.py` — Sports Analyst Prompt

The generation prompt tells the LLM to act as a professional sports analyst. It must:
- Cite specific events (minute + player)
- Be concise but insightful
- Say when it doesn't have enough context

Context is passed as a single `{context}` variable that combines tool results and retrieved documents.

### `retrieval_grader.py` — Document Relevance

Binary yes/no check: "Is this document relevant to the question?" Uses structured output with a `GradeDocuments` model. If a document is graded "no", the node sets a `web_search` flag.

### `hallucination_grader.py` — Grounding Check

Binary true/false: "Is the generation grounded in the source documents?" Checks that player names, minutes, and events cited actually appear in the context. Returns `False` if the LLM fabricated events.

### `answer_grader.py` — Answer Quality

Binary true/false: "Does the response actually answer the question?" Catches cases where the LLM gives a valid-sounding but tangential response.

## Nodes (`graph/nodes/`)

Each node is a function that takes `GraphState` and returns a dict of state updates.

### `tool_execute.py`

The most complex node. It:
1. Gets all available tools via `get_all_tools()`
2. Binds them to the LLM with `llm.bind_tools(tools)`
3. Sends the question to the LLM, which decides which tools to call
4. Executes the tool calls and collects results
5. Wraps results as `Document` objects for the grading step

### `event_search.py`

Runs `vector_store.search()` with the question and match_id. Returns the top 5 matching documents plus source metadata for attribution.

### `grade_documents.py`

Iterates over each document and grades it for relevance. Filters out irrelevant ones. Sets `web_search = True` if any document was irrelevant.

### `generate.py`

Combines `tool_results` and `documents` into a single context string, then calls the generation chain. Increments the `retries` counter.

### `web_search.py`

Fallback node using Tavily Search. Runs a web search for the question and adds the results to the documents list.

## Retry Logic

`grade_generation()` is the quality gate. After the LLM generates a response, it checks:

1. **Hallucination check** — if the response isn't grounded in the data, route back to `generate` (re-try with the same context)
2. **Answer check** — if grounded but doesn't answer the question, route back to `event_search` (try different context)
3. **Max retries** — after 3 attempts, accept whatever was generated. This prevents infinite loops.

## Building the Graph (`graph/graph.py`)

The `build_graph()` function assembles everything:
- Adds all 6 nodes
- Sets `route_question` as the conditional entry point
- Wires edges between nodes
- Returns a compiled graph

`app = build_graph()` creates the default instance. The Streamlit UI and CLI both call `app.invoke({"question": ..., "match_id": ..., "retries": 0})`.
