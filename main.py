"""CLI entry point for the Streaming Sports Intelligence Agent.

Loads a fixture match, ingests it into both stores, configures the tools,
and runs the LangGraph agent with a sample question.
"""

from dotenv import load_dotenv

load_dotenv()

from fixtures import load_fixture
from graph.tools import configure
from storage.event_store import EventStore
from storage.vector_store import SportVectorStore
from streaming.pipeline import IngestionPipeline


def main():
    print("Streaming Sports Intelligence Agent")
    print("=" * 50)

    # 1. Set up stores
    print("\n[1] Setting up stores...")
    event_store = EventStore("./data/sports.db")
    vector_store = SportVectorStore(
        collection_name="sports-events",
        persist_directory="./data/chroma",
    )

    # 2. Ingest fixture match
    print("[2] Ingesting match data...")
    feed = load_fixture("match_001")
    pipeline = IngestionPipeline(event_store, vector_store)
    count = pipeline.ingest_match(feed)
    print(f"    Ingested {count} events for {feed.metadata.home_team.name} vs {feed.metadata.away_team.name}")

    # 3. Configure tools with store instances
    print("[3] Configuring agent tools...")
    configure(event_store=event_store, vector_store=vector_store)

    # 4. Build and run the agent
    print("[4] Building agent graph...")
    from graph.graph import build_graph

    app = build_graph()

    # 5. Ask questions
    questions = [
        "What changed after the substitution?",
        "Summarise the match so far.",
        "Which player had the biggest impact?",
    ]

    for question in questions:
        print(f"\n{'=' * 60}")
        print(f"Q: {question}")
        print("-" * 60)

        result = app.invoke(
            input={
                "question": question,
                "match_id": "match_001",
                "retries": 0,
            }
        )

        print(f"\nA: {result['generation']}")

        if result.get("sources"):
            print(f"\nSources: {len(result['sources'])} evidence items")


if __name__ == "__main__":
    main()
