# 08 — Testing

113 tests across 8 test files. A mix of pure unit tests (no API calls) and integration tests (require OpenAI API key).

## Test Files

| File | Tests | Needs API? | What It Covers |
|------|-------|------------|----------------|
| `tests/test_models.py` | 17 | No | Pydantic models, fixture loading, validation, serialization round-trips |
| `tests/test_streaming.py` | 17 | No | Mock Kafka (registry, producer, consumer), batch/realtime modes, message ordering |
| `tests/test_event_store.py` | 28 | No | SQLite insert/query for all methods, score computation, player stats, round-trip fidelity |
| `tests/test_vector_store.py` | 11 | Yes | Chroma indexing, semantic search, metadata filters, score context in documents |
| `tests/test_pipeline.py` | 9 | Yes | End-to-end ingestion (produce → consume → both stores), score tracking, normalisation |
| `tests/test_tools.py` | 14 | Yes | Each tool independently with fixture data, edge cases (empty results, nonexistent players) |
| `tests/test_graph.py` | 5 | Yes | Full graph invocations with real questions, checks answer content and grounding |
| `graph/chains/tests/test_chains.py` | 12 | Yes | Router classification, retrieval grading, generation output, hallucination detection, answer grading |

## Running Tests

```bash
# All tests
pytest -v

# Unit tests only (fast, no API key needed)
pytest tests/test_models.py tests/test_streaming.py tests/test_event_store.py -v

# Integration tests (need OPENAI_API_KEY in .env)
pytest tests/test_vector_store.py tests/test_pipeline.py tests/test_tools.py tests/test_graph.py -v

# Chain tests
pytest graph/chains/tests/ -v
```

## Test Design Patterns

- **Module-scoped fixtures** for expensive setup: `test_tools.py` and `test_graph.py` ingest the match once per module, not per test.
- **`@needs_openai` skip marker** — tests that need the API are skipped if `OPENAI_API_KEY` isn't set, so CI can still run the unit tests.
- **In-memory stores** — every test suite uses `EventStore(":memory:")` and a fresh Chroma collection, ensuring test isolation.
- **Round-trip assertions** — several tests verify that data survives serialize → store → retrieve cycles without loss (coordinates, additional_info, event types).
