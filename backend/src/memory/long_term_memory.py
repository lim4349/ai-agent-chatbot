"""Long-term cross-session memory store using ChromaDB."""

import hashlib
import json
from datetime import datetime
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


class LongTermMemory:
    """Long-term memory for cross-session user data and topic storage.

    Uses ChromaDB for vector storage to enable similarity search across sessions.
    Stores user profiles, topic summaries, and session relationships.
    """

    def __init__(
        self,
        embedding_function=None,
        persist_directory: str | None = None,
        anonymize: bool = True,
    ):
        """Initialize long-term memory store.

        Args:
            embedding_function: Optional embedding function for vector search
            persist_directory: Directory to persist ChromaDB data
            anonymize: Whether to anonymize sensitive user data
        """
        self.anonymize = anonymize
        self._persist_directory = persist_directory
        self._embedding_function = embedding_function

        # In-memory fallback when ChromaDB is not available
        self._user_profiles: dict[str, dict] = {}
        self._topic_summaries: dict[str, list[dict]] = {}
        self._session_topics: dict[str, set[str]] = {}
        self._topic_sessions: dict[str, set[str]] = {}
        self._facts: dict[str, list[dict]] = {}

        # Try to import and initialize ChromaDB
        self._chroma_client = None
        self._user_collection = None
        self._topic_collection = None
        self._fact_collection = None

        try:
            import chromadb
            from chromadb.config import Settings

            if persist_directory:
                self._chroma_client = chromadb.PersistentClient(
                    path=persist_directory,
                    settings=Settings(anonymized_telemetry=False),
                )
            else:
                self._chroma_client = chromadb.Client(settings=Settings(anonymized_telemetry=False))

            # Get or create collections
            self._user_collection = self._chroma_client.get_or_create_collection(
                name="user_profiles",
                embedding_function=self._embedding_function,
            )
            self._topic_collection = self._chroma_client.get_or_create_collection(
                name="topic_summaries",
                embedding_function=self._embedding_function,
            )
            self._fact_collection = self._chroma_client.get_or_create_collection(
                name="user_facts",
                embedding_function=self._embedding_function,
            )

            logger.info("long_term_memory_initialized", chroma_available=True)
        except ImportError:
            logger.warning(
                "chroma_not_available",
                message="ChromaDB not installed, using in-memory fallback",
            )
        except Exception as e:
            logger.error(
                "chroma_init_failed",
                error=str(e),
                message="Using in-memory fallback",
            )

    def _anonymize(self, text: str) -> str:
        """Anonymize potentially sensitive information."""
        if not self.anonymize:
            return text

        # Simple anonymization: hash emails, phone numbers, etc.
        import re

        # Replace email addresses
        text = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "[EMAIL_REDACTED]",
            text,
        )
        # Replace phone numbers (basic patterns)
        text = re.sub(
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
            "[PHONE_REDACTED]",
            text,
        )

        return text

    def _generate_id(self, *parts: str) -> str:
        """Generate a unique ID from parts."""
        content = "|".join(parts)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def store_user_fact(
        self,
        user_id: str,
        fact: str,
        category: str = "general",
        confidence: float = 1.0,
    ) -> None:
        """Store a fact about a user.

        Args:
            user_id: Unique user identifier
            fact: The fact to store
            category: Category of the fact (interests, preferences, etc.)
            confidence: Confidence level of the fact (0.0-1.0)
        """
        anonymized_fact = self._anonymize(fact)
        timestamp = datetime.utcnow().isoformat()

        fact_data = {
            "user_id": user_id,
            "fact": anonymized_fact,
            "category": category,
            "confidence": confidence,
            "timestamp": timestamp,
        }

        # Store in memory fallback
        if user_id not in self._facts:
            self._facts[user_id] = []
        self._facts[user_id].append(fact_data)

        # Store in ChromaDB if available
        if self._fact_collection:
            try:
                doc_id = self._generate_id(user_id, anonymized_fact, timestamp)
                self._fact_collection.add(
                    documents=[anonymized_fact],
                    metadatas=[
                        {
                            "user_id": user_id,
                            "category": category,
                            "confidence": confidence,
                            "timestamp": timestamp,
                        }
                    ],
                    ids=[doc_id],
                )
            except Exception as e:
                logger.error("failed_to_store_fact", error=str(e))

        logger.debug(
            "user_fact_stored",
            user_id=user_id,
            category=category,
            fact_length=len(anonymized_fact),
        )

    async def get_user_profile(self, user_id: str) -> dict[str, Any]:
        """Get complete user profile including all facts.

        Args:
            user_id: Unique user identifier

        Returns:
            Dictionary with user profile data
        """
        profile = {
            "user_id": user_id,
            "facts": {},
            "interests": [],
            "preferences": {},
            "technical_level": None,
            "response_style": None,
            "expertise_areas": [],
            "created_at": None,
            "updated_at": None,
        }

        # Get from in-memory store
        if user_id in self._user_profiles:
            profile.update(self._user_profiles[user_id])

        # Get facts
        if user_id in self._facts:
            for fact_data in self._facts[user_id]:
                category = fact_data["category"]
                if category not in profile["facts"]:
                    profile["facts"][category] = []
                profile["facts"][category].append(fact_data)

        # Query ChromaDB if available
        if self._fact_collection:
            try:
                results = self._fact_collection.query(
                    query_texts=[""],
                    where={"user_id": user_id},
                    n_results=100,
                )

                for i, doc in enumerate(results.get("documents", [[]])[0]):
                    metadata = results["metadatas"][0][i]
                    category = metadata.get("category", "general")

                    if category not in profile["facts"]:
                        profile["facts"][category] = []

                    # Check if already in profile from memory
                    existing = any(f["fact"] == doc for f in profile["facts"][category])
                    if not existing:
                        profile["facts"][category].append(
                            {
                                "fact": doc,
                                "category": category,
                                "confidence": metadata.get("confidence", 1.0),
                                "timestamp": metadata.get("timestamp"),
                            }
                        )
            except Exception as e:
                logger.error("failed_to_query_facts", error=str(e))

        return profile

    async def update_user_profile(
        self,
        user_id: str,
        updates: dict[str, Any],
    ) -> None:
        """Update user profile with new information.

        Args:
            user_id: Unique user identifier
            updates: Dictionary of profile fields to update
        """
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = {
                "created_at": datetime.utcnow().isoformat(),
            }

        # Update profile
        for key, value in updates.items():
            if key == "facts":
                # Handle facts separately
                for fact in value:
                    await self.store_user_fact(
                        user_id,
                        fact["fact"],
                        fact.get("category", "general"),
                        fact.get("confidence", 1.0),
                    )
            else:
                self._user_profiles[user_id][key] = value

        self._user_profiles[user_id]["updated_at"] = datetime.utcnow().isoformat()

        # Store in ChromaDB if available
        if self._user_collection:
            try:
                profile_text = json.dumps(
                    {
                        k: v
                        for k, v in self._user_profiles[user_id].items()
                        if k not in ("created_at", "updated_at")
                    }
                )
                doc_id = self._generate_id(user_id)

                self._user_collection.upsert(
                    documents=[profile_text],
                    metadatas=[
                        {
                            "user_id": user_id,
                            "updated_at": self._user_profiles[user_id]["updated_at"],
                        }
                    ],
                    ids=[doc_id],
                )
            except Exception as e:
                logger.error("failed_to_update_profile", error=str(e))

        logger.debug("user_profile_updated", user_id=user_id, fields=list(updates.keys()))

    async def store_topic_summary(
        self,
        topic: str,
        summary: str,
        session_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Store a summary for a topic.

        Args:
            topic: Topic identifier
            summary: Summary text
            session_id: Optional session that generated this summary
            metadata: Additional metadata
        """
        timestamp = datetime.utcnow().isoformat()

        summary_data = {
            "topic": topic,
            "summary": summary,
            "session_id": session_id,
            "timestamp": timestamp,
            "metadata": metadata or {},
        }

        # Store in memory fallback
        if topic not in self._topic_summaries:
            self._topic_summaries[topic] = []
        self._topic_summaries[topic].append(summary_data)

        # Link session to topic
        if session_id:
            if session_id not in self._session_topics:
                self._session_topics[session_id] = set()
            self._session_topics[session_id].add(topic)

            if topic not in self._topic_sessions:
                self._topic_sessions[topic] = set()
            self._topic_sessions[topic].add(session_id)

        # Store in ChromaDB if available
        if self._topic_collection:
            try:
                doc_id = self._generate_id(topic, summary, timestamp)
                self._topic_collection.add(
                    documents=[summary],
                    metadatas=[
                        {
                            "topic": topic,
                            "session_id": session_id,
                            "timestamp": timestamp,
                            **(metadata or {}),
                        }
                    ],
                    ids=[doc_id],
                )
            except Exception as e:
                logger.error("failed_to_store_topic", error=str(e))

        logger.debug(
            "topic_summary_stored",
            topic=topic,
            session_id=session_id,
            summary_length=len(summary),
        )

    async def get_topic_history(self, topic: str, limit: int = 10) -> list[dict]:
        """Get history of summaries for a topic.

        Args:
            topic: Topic identifier
            limit: Maximum number of summaries to return

        Returns:
            List of summary entries
        """
        # Get from in-memory store
        summaries = self._topic_summaries.get(topic, [])

        # Query ChromaDB if available
        if self._topic_collection:
            try:
                results = self._topic_collection.query(
                    query_texts=[topic],
                    where={"topic": topic},
                    n_results=limit,
                )

                for i, doc in enumerate(results.get("documents", [[]])[0]):
                    metadata = results["metadatas"][0][i]
                    entry = {
                        "topic": topic,
                        "summary": doc,
                        "session_id": metadata.get("session_id"),
                        "timestamp": metadata.get("timestamp"),
                        "metadata": {
                            k: v
                            for k, v in metadata.items()
                            if k not in ("topic", "session_id", "timestamp")
                        },
                    }
                    # Check if already in list
                    if not any(s["timestamp"] == entry["timestamp"] for s in summaries):
                        summaries.append(entry)
            except Exception as e:
                logger.error("failed_to_query_topics", error=str(e))

        # Sort by timestamp and limit
        summaries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return summaries[:limit]

    async def get_related_sessions(self, session_id: str) -> list[str]:
        """Get sessions related to the given session by topic.

        Args:
            session_id: Session identifier

        Returns:
            List of related session IDs
        """
        related = set()

        # Get from in-memory store
        topics = self._session_topics.get(session_id, set())
        for topic in topics:
            related.update(self._topic_sessions.get(topic, set()))

        # Remove self
        related.discard(session_id)

        return list(related)

    async def search_similar_facts(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Search for facts similar to the query.

        Args:
            user_id: User to search within
            query: Search query
            top_k: Number of results to return

        Returns:
            List of similar facts
        """
        if not self._fact_collection:
            # Fallback: simple text search in memory
            facts = self._facts.get(user_id, [])
            results = []
            query_lower = query.lower()
            for fact in facts:
                if query_lower in fact["fact"].lower():
                    results.append(fact)
            return results[:top_k]

        try:
            results = self._fact_collection.query(
                query_texts=[query],
                where={"user_id": user_id},
                n_results=top_k,
            )

            facts = []
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                metadata = results["metadatas"][0][i]
                facts.append(
                    {
                        "fact": doc,
                        "category": metadata.get("category", "general"),
                        "confidence": metadata.get("confidence", 1.0),
                        "timestamp": metadata.get("timestamp"),
                    }
                )
            return facts
        except Exception as e:
            logger.error("similarity_search_failed", error=str(e))
            return []

    async def search_topics(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Search for topics similar to the query.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of topic summaries
        """
        if not self._topic_collection:
            # Fallback: simple text search in memory
            results = []
            query_lower = query.lower()
            for _topic, summaries in self._topic_summaries.items():
                for summary_data in summaries:
                    if query_lower in summary_data["summary"].lower():
                        results.append(summary_data)
            return results[:top_k]

        try:
            results = self._topic_collection.query(
                query_texts=[query],
                n_results=top_k,
            )

            topics = []
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                metadata = results["metadatas"][0][i]
                topics.append(
                    {
                        "topic": metadata.get("topic", "unknown"),
                        "summary": doc,
                        "session_id": metadata.get("session_id"),
                        "timestamp": metadata.get("timestamp"),
                    }
                )
            return topics
        except Exception as e:
            logger.error("topic_search_failed", error=str(e))
            return []

    async def clear_user_data(self, user_id: str) -> None:
        """Clear all data for a user (GDPR compliance).

        Args:
            user_id: User to clear data for
        """
        # Clear from memory
        self._user_profiles.pop(user_id, None)
        self._facts.pop(user_id, None)

        # Clear from ChromaDB
        if self._fact_collection:
            try:
                results = self._fact_collection.get(where={"user_id": user_id})
                if results and results["ids"]:
                    self._fact_collection.delete(ids=results["ids"])
            except Exception as e:
                logger.error("failed_to_clear_facts", error=str(e))

        if self._user_collection:
            try:
                doc_id = self._generate_id(user_id)
                self._user_collection.delete(ids=[doc_id])
            except Exception as e:
                logger.error("failed_to_clear_profile", error=str(e))

        logger.info("user_data_cleared", user_id=user_id)
