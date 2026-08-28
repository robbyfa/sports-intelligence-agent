"""Chroma-backed vector store for semantic retrieval of sports events.

Each event's narrative text is enriched with contextual metadata and embedded
into Chroma for semantic search.  Replaces the old ``ingestion.py`` which
loaded web URLs.

Usage::

    from storage.vector_store import SportVectorStore

    vs = SportVectorStore()  # in-memory for tests
    vs.index_match(feed)
    docs = vs.search("What happened after the red card?", match_id="match_001")
"""

from __future__ import annotations

from typing import Optional

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from models.events import EventType, MatchEvent, MatchFeed, MatchMetadata


class SportVectorStore:
    """Wraps Chroma with sports-event-specific indexing and retrieval.

    Args:
        collection_name: Chroma collection name.
        persist_directory: Directory for on-disk persistence.
                          Pass ``None`` for a purely in-memory store.
        embedding: Embedding function. Defaults to ``OpenAIEmbeddings``.
    """

    def __init__(
        self,
        collection_name: str = "sports-events",
        persist_directory: Optional[str] = None,
        embedding=None,
    ) -> None:
        self._embedding = embedding or OpenAIEmbeddings()
        kwargs = {
            "collection_name": collection_name,
            "embedding_function": self._embedding,
        }
        if persist_directory:
            kwargs["persist_directory"] = persist_directory
        self._store = Chroma(**kwargs)
        self._collection_name = collection_name

    # ── Indexing ───────────────────────────────────────────────────

    def index_event(
        self,
        event: MatchEvent,
        match_metadata: MatchMetadata,
        score_state: Optional[dict] = None,
    ) -> str:
        """Index a single event into Chroma.

        The document's ``page_content`` combines the narrative text with
        structured context (minute, player, team, event type, current score)
        so the embeddings capture both semantics and match context.

        Args:
            event: The event to index.
            match_metadata: Match-level context.
            score_state: Optional dict ``{"home": int, "away": int}`` for
                         the score at the time of this event.

        Returns:
            The document ID used in Chroma.
        """
        doc = self._event_to_document(event, match_metadata, score_state)
        self._store.add_documents([doc], ids=[event.event_id])
        return event.event_id

    def index_match(self, feed: MatchFeed) -> int:
        """Bulk-index all events from a match feed.

        Tracks running score state so each document reflects the score
        at the moment that event occurred.

        Returns:
            Number of documents indexed.
        """
        docs: list[Document] = []
        ids: list[str] = []
        score = {"home": 0, "away": 0}

        for event in feed.events_by_minute():
            # Update score before creating the document so the goal
            # event itself reflects the new score
            if event.event_type == EventType.GOAL:
                if event.team == feed.metadata.home_team.name:
                    score["home"] += 1
                elif event.team == feed.metadata.away_team.name:
                    score["away"] += 1

            doc = self._event_to_document(event, feed.metadata, dict(score))
            docs.append(doc)
            ids.append(event.event_id)

        if docs:
            self._store.add_documents(docs, ids=ids)
        return len(docs)

    # ── Search ─────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        match_id: Optional[str] = None,
        filters: Optional[dict] = None,
        k: int = 5,
    ) -> list[Document]:
        """Semantic search over indexed events.

        Args:
            query: Natural-language query.
            match_id: If provided, restricts results to this match.
            filters: Additional Chroma metadata filters
                     (e.g. ``{"event_type": "goal"}``).
            k: Number of results to return.

        Returns:
            List of LangChain ``Document`` objects with metadata.
        """
        where_filter = self._build_filter(match_id, filters)
        kwargs = {"k": k}
        if where_filter:
            kwargs["filter"] = where_filter
        return self._store.similarity_search(query, **kwargs)

    def as_retriever(self, **kwargs):
        """Return a LangChain retriever wrapping this store."""
        return self._store.as_retriever(**kwargs)

    # ── Internal ───────────────────────────────────────────────────

    def _event_to_document(
        self,
        event: MatchEvent,
        metadata: MatchMetadata,
        score_state: Optional[dict] = None,
    ) -> Document:
        """Convert a MatchEvent into a LangChain Document for embedding."""
        # Build enriched content that gives the embedding model full context
        parts = [
            f"[{metadata.home_team.short_name} vs {metadata.away_team.short_name}]",
            f"[Minute {event.minute}']",
        ]
        if score_state:
            parts.append(
                f"[Score: {metadata.home_team.short_name} {score_state['home']}"
                f" - {score_state['away']} {metadata.away_team.short_name}]"
            )
        if event.player_name:
            parts.append(f"[{event.player_name} ({event.team})]")
        parts.append(f"[{event.event_type.value.replace('_', ' ').title()}]")
        parts.append(event.narrative_text)

        page_content = " ".join(parts)

        doc_metadata = {
            "match_id": event.match_id,
            "event_id": event.event_id,
            "minute": event.minute,
            "event_type": event.event_type.value,
            "competition": metadata.competition,
        }
        if event.player_name:
            doc_metadata["player_name"] = event.player_name
        if event.team:
            doc_metadata["team"] = event.team
        if event.xg is not None:
            doc_metadata["xg"] = event.xg

        return Document(page_content=page_content, metadata=doc_metadata)

    def _build_filter(
        self,
        match_id: Optional[str],
        filters: Optional[dict],
    ) -> Optional[dict]:
        """Build a Chroma ``where`` filter from optional constraints."""
        conditions = []
        if match_id:
            conditions.append({"match_id": match_id})
        if filters:
            for key, value in filters.items():
                conditions.append({key: value})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def reset(self) -> None:
        """Delete all documents. Useful for tests."""
        self._store.delete_collection()
        # Recreate with the same name
        kwargs = {
            "collection_name": self._collection_name,
            "embedding_function": self._embedding,
        }
        self._store = Chroma(**kwargs)
