"""Long-term cross-session memory store using Supabase with in-memory fallback."""

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


class LongTermMemory:
    """Long-term memory for cross-session user data and topic storage.

    Uses Supabase PostgreSQL for persistent storage with in-memory fallback.
    Stores user profiles, topic summaries, and session relationships.
    """

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        anonymize: bool = True,
    ):
        """Initialize long-term memory store.

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service key
            anonymize: Whether to anonymize sensitive user data
        """
        self.anonymize = anonymize
        self._supabase_url = supabase_url
        self._supabase_key = supabase_key

        # In-memory fallback
        self._user_profiles: dict[str, dict] = {}
        self._topic_summaries: dict[str, list[dict]] = {}
        self._session_topics: dict[str, set[str]] = {}
        self._topic_sessions: dict[str, set[str]] = {}
        self._facts: dict[str, list[dict]] = {}

        # Try to initialize Supabase client
        self._client = None
        self._use_supabase = False

        if supabase_url and supabase_key:
            try:
                from supabase import create_client

                self._client = create_client(supabase_url, supabase_key)
                # Test connection
                self._client.table("user_profiles").select("id").limit(1).execute()
                self._use_supabase = True
                logger.info("long_term_memory_initialized", supabase=True)
            except ImportError:
                logger.warning(
                    "supabase_not_available",
                    message="Supabase client not installed, using in-memory fallback",
                )
            except Exception as e:
                logger.warning(
                    "supabase_connection_failed",
                    error=str(e),
                    message="Using in-memory fallback",
                )
        else:
            logger.info("long_term_memory_initialized", supabase=False, in_memory=True)

    _MIN_FACT_CONFIDENCE = 0.8
    _MIN_TOPIC_SUMMARY_LENGTH = 24
    _GENERIC_FACT_PREFIXES = (
        "the user",
        "user prefers",
        "user likes",
        "user uses",
    )

    def _anonymize(self, text: str) -> str:
        """Anonymize potentially sensitive information."""
        if not self.anonymize:
            return text

        # Replace URLs and repository-like references first
        text = re.sub(r"https?://\S+", "[URL_REDACTED]", text)
        text = re.sub(r"\bgithub\.com/\S+\b", "[REPO_REDACTED]", text, flags=re.IGNORECASE)

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
        # Replace IPv4 addresses
        text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP_REDACTED]", text)
        # Replace @handles and common ticket references
        text = re.sub(r"(?<!\w)@[A-Za-z0-9_][A-Za-z0-9_.-]*", "[HANDLE_REDACTED]", text)
        text = re.sub(r"\b[A-Z]{2,10}-\d{1,6}\b", "[TICKET_REDACTED]", text)

        return text

    def _normalize_text(self, text: str) -> str:
        """Normalize text for dedupe checks."""
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        normalized = re.sub(r"[^\w\s\[\]]", "", normalized)
        return normalized

    def _is_fact_worth_storing(self, fact: str, confidence: float) -> bool:
        """Reject vague or low-confidence facts before persistence."""
        normalized = self._normalize_text(fact)
        if confidence < self._MIN_FACT_CONFIDENCE:
            return False
        if len(normalized) < 12:
            return False
        return not any(normalized.startswith(prefix) for prefix in self._GENERIC_FACT_PREFIXES)

    def _find_fact_index(
        self,
        facts: list[dict[str, Any]],
        category: str,
        normalized_fact: str,
    ) -> int | None:
        """Find an existing fact with matching normalized content."""
        for index, fact_data in enumerate(facts):
            if fact_data["category"] != category:
                continue

            existing_normalized = self._normalize_text(fact_data["fact"])
            if (
                existing_normalized == normalized_fact
                or normalized_fact in existing_normalized
                or existing_normalized in normalized_fact
            ):
                return index

        return None

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
        if not self._is_fact_worth_storing(anonymized_fact, confidence):
            logger.debug(
                "user_fact_skipped",
                user_id=user_id,
                category=category,
                reason="low_confidence_or_generic",
            )
            return

        timestamp = datetime.now(tz=UTC).isoformat()
        normalized_fact = self._normalize_text(anonymized_fact)

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
        existing_index = self._find_fact_index(self._facts[user_id], category, normalized_fact)
        if existing_index is None:
            self._facts[user_id].append(fact_data)
        elif confidence >= self._facts[user_id][existing_index].get("confidence", 0):
            self._facts[user_id][existing_index] = fact_data

        # Store in Supabase if available
        if self._use_supabase and self._client:
            try:
                existing_facts = (
                    self._client.table("user_facts")
                    .select("*")
                    .eq("user_id", user_id)
                    .eq("category", category)
                    .execute()
                )

                matching_row = None
                for row in existing_facts.data:
                    row_normalized = self._normalize_text(row["fact"])
                    if (
                        row_normalized == normalized_fact
                        or normalized_fact in row_normalized
                        or row_normalized in normalized_fact
                    ):
                        matching_row = row
                        break

                if matching_row:
                    row_id = matching_row.get("id")
                    if row_id and confidence >= matching_row.get("confidence", 0):
                        self._client.table("user_facts").update(
                            {
                                "fact": anonymized_fact,
                                "confidence": confidence,
                            }
                        ).eq("id", row_id).execute()
                else:
                    self._client.table("user_facts").insert(
                        {
                            "user_id": user_id,
                            "fact": anonymized_fact,
                            "category": category,
                            "confidence": confidence,
                        }
                    ).execute()
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

        # Get facts from memory
        if user_id in self._facts:
            for fact_data in self._facts[user_id]:
                category = fact_data["category"]
                if category not in profile["facts"]:
                    profile["facts"][category] = []
                profile["facts"][category].append(fact_data)

        # Get from Supabase if available
        if self._use_supabase and self._client:
            try:
                # Get profile data
                profile_result = (
                    self._client.table("user_profiles")
                    .select("*")
                    .eq("user_id", user_id)
                    .maybe_single()
                    .execute()
                )
                if profile_result.data:
                    profile_data = profile_result.data["profile_data"]
                    profile.update(profile_data)
                    profile["created_at"] = profile_result.data.get("created_at")
                    profile["updated_at"] = profile_result.data.get("updated_at")

                # Get facts
                facts_result = (
                    self._client.table("user_facts").select("*").eq("user_id", user_id).execute()
                )
                for fact_row in facts_result.data:
                    category = fact_row["category"]
                    if category not in profile["facts"]:
                        profile["facts"][category] = []

                    # Check if already in profile from memory
                    fact_text = fact_row["fact"]
                    existing = any(f["fact"] == fact_text for f in profile["facts"][category])
                    if not existing:
                        profile["facts"][category].append(
                            {
                                "fact": fact_text,
                                "category": category,
                                "confidence": fact_row.get("confidence", 0.5),
                                "timestamp": fact_row.get("created_at"),
                            }
                        )
            except Exception as e:
                logger.error("failed_to_query_profile", error=str(e))

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
                "created_at": datetime.now(tz=UTC).isoformat(),
            }

        # Update profile in memory
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

        self._user_profiles[user_id]["updated_at"] = datetime.now(tz=UTC).isoformat()

        # Update in Supabase if available
        if self._use_supabase and self._client:
            try:
                # Prepare profile data (exclude facts from profile_data)
                profile_data = {
                    k: v
                    for k, v in self._user_profiles[user_id].items()
                    if k not in ("created_at", "updated_at", "facts")
                }

                # Upsert profile
                self._client.table("user_profiles").upsert(
                    {
                        "user_id": user_id,
                        "profile_data": profile_data,
                    }
                ).execute()
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
        clean_topic = " ".join(topic.strip().split())
        clean_summary = self._anonymize(summary.strip())
        if len(clean_summary) < self._MIN_TOPIC_SUMMARY_LENGTH:
            logger.debug(
                "topic_summary_skipped",
                topic=clean_topic,
                session_id=session_id,
                reason="summary_too_short",
            )
            return

        timestamp = datetime.now(tz=UTC).isoformat()

        summary_data = {
            "topic": clean_topic,
            "summary": clean_summary,
            "session_id": session_id,
            "timestamp": timestamp,
            "metadata": metadata or {},
        }

        # Store in memory fallback
        if clean_topic not in self._topic_summaries:
            self._topic_summaries[clean_topic] = []
        replaced = False
        if session_id:
            for index, existing in enumerate(self._topic_summaries[clean_topic]):
                if existing.get("session_id") == session_id:
                    self._topic_summaries[clean_topic][index] = summary_data
                    replaced = True
                    break
        if not replaced:
            self._topic_summaries[clean_topic].append(summary_data)

        # Link session to topic
        if session_id:
            if session_id not in self._session_topics:
                self._session_topics[session_id] = set()
            self._session_topics[session_id].add(clean_topic)

            if clean_topic not in self._topic_sessions:
                self._topic_sessions[clean_topic] = set()
            self._topic_sessions[clean_topic].add(session_id)

        # Store in Supabase if available
        if self._use_supabase and self._client:
            try:
                if session_id:
                    existing_rows = (
                        self._client.table("topic_summaries")
                        .select("*")
                        .eq("session_id", session_id)
                        .eq("topic", clean_topic)
                        .execute()
                    )
                else:
                    existing_rows = None

                if existing_rows and existing_rows.data:
                    row_id = existing_rows.data[0].get("id")
                    if row_id:
                        self._client.table("topic_summaries").update(
                            {
                                "summary": clean_summary,
                                "metadata": metadata or {},
                            }
                        ).eq("id", row_id).execute()
                    else:
                        self._client.table("topic_summaries").update(
                            {
                                "summary": clean_summary,
                                "metadata": metadata or {},
                            }
                        ).eq("session_id", session_id).eq("topic", clean_topic).execute()
                else:
                    self._client.table("topic_summaries").insert(
                        {
                            "topic": clean_topic,
                            "summary": clean_summary,
                            "session_id": session_id,
                            "metadata": metadata or {},
                        }
                    ).execute()
            except Exception as e:
                logger.error("failed_to_store_topic", error=str(e))

        logger.debug(
            "topic_summary_stored",
            topic=clean_topic,
            session_id=session_id,
            summary_length=len(clean_summary),
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

        # Get from Supabase if available
        if self._use_supabase and self._client:
            try:
                result = (
                    self._client.table("topic_summaries")
                    .select("*")
                    .eq("topic", topic)
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                for row in result.data:
                    entry = {
                        "topic": row["topic"],
                        "summary": row["summary"],
                        "session_id": row.get("session_id"),
                        "timestamp": row.get("created_at"),
                        "metadata": row.get("metadata", {}),
                    }
                    # Check if already in list
                    if not any(
                        s["timestamp"] == entry["timestamp"] and s["summary"] == entry["summary"]
                        for s in summaries
                    ):
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

        # Get from Supabase if available
        if self._use_supabase and self._client:
            try:
                # Find all topics for this session
                result = (
                    self._client.table("topic_summaries")
                    .select("topic")
                    .eq("session_id", session_id)
                    .execute()
                )
                topics_from_db = {row["topic"] for row in result.data}

                # Find all sessions for those topics
                for topic in topics_from_db:
                    sessions_result = (
                        self._client.table("topic_summaries")
                        .select("session_id")
                        .eq("topic", topic)
                        .not_.is_("session_id", None)
                        .execute()
                    )
                    for row in sessions_result.data:
                        if row["session_id"]:
                            related.add(row["session_id"])
            except Exception as e:
                logger.error("failed_to_query_related_sessions", error=str(e))

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
        # Simple text search (ILIKE for case-insensitive matching)
        if self._use_supabase and self._client:
            try:
                result = (
                    self._client.table("user_facts")
                    .select("*")
                    .eq("user_id", user_id)
                    .ilike("fact", f"%{query}%")
                    .limit(top_k)
                    .execute()
                )
                return [
                    {
                        "fact": row["fact"],
                        "category": row.get("category", "general"),
                        "confidence": row.get("confidence", 0.5),
                        "timestamp": row.get("created_at"),
                    }
                    for row in result.data
                ]
            except Exception as e:
                logger.error("similarity_search_failed", error=str(e))

        # Fallback: simple text search in memory
        facts = self._facts.get(user_id, [])
        results = []
        query_lower = query.lower()
        for fact in facts:
            if query_lower in fact["fact"].lower():
                results.append(fact)
        return results[:top_k]

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
        # Search in summary text and topic name
        if self._use_supabase and self._client:
            try:
                # Search in summary text
                result = (
                    self._client.table("topic_summaries")
                    .select("*")
                    .or_(f"topic.ilike.%{query}%,summary.ilike.%{query}%")
                    .order("created_at", desc=True)
                    .limit(top_k)
                    .execute()
                )
                return [
                    {
                        "topic": row["topic"],
                        "summary": row["summary"],
                        "session_id": row.get("session_id"),
                        "timestamp": row.get("created_at"),
                    }
                    for row in result.data
                ]
            except Exception as e:
                logger.error("topic_search_failed", error=str(e))

        # Fallback: simple text search in memory
        results = []
        query_lower = query.lower()
        for _topic, summaries in self._topic_summaries.items():
            for summary_data in summaries:
                if query_lower in summary_data["summary"].lower() or query_lower in _topic.lower():
                    results.append(summary_data)
        return results[:top_k]

    async def clear_user_data(self, user_id: str) -> None:
        """Clear all data for a user (GDPR compliance).

        Args:
            user_id: User to clear data for
        """
        # Clear from memory
        self._user_profiles.pop(user_id, None)
        self._facts.pop(user_id, None)

        # Clear from Supabase
        if self._use_supabase and self._client:
            try:
                # Delete facts
                self._client.table("user_facts").delete().eq("user_id", user_id).execute()
                # Delete profile
                self._client.table("user_profiles").delete().eq("user_id", user_id).execute()
            except Exception as e:
                logger.error("failed_to_clear_user_data", error=str(e))

        logger.info("user_data_cleared", user_id=user_id)

    async def delete_session_topics(self, session_id: str) -> int:
        """Delete all topic summaries for a session.

        Args:
            session_id: Session identifier

        Returns:
            Number of deleted entries
        """
        deleted_count = 0

        # Clear from in-memory store
        if session_id in self._session_topics:
            topics = self._session_topics.pop(session_id)
            for topic in topics:
                # Remove this session from topic's session list
                if topic in self._topic_sessions:
                    self._topic_sessions[topic].discard(session_id)
                # Remove summaries for this session from memory
                if topic in self._topic_summaries:
                    self._topic_summaries[topic] = [
                        s for s in self._topic_summaries[topic] if s.get("session_id") != session_id
                    ]
            deleted_count = len(topics)

        # Delete from Supabase
        if self._use_supabase and self._client:
            try:
                result = (
                    self._client.table("topic_summaries")
                    .delete()
                    .eq("session_id", session_id)
                    .execute()
                )
                deleted_count = max(deleted_count, len(result.data))
            except Exception as e:
                logger.error("failed_to_delete_session_topics", error=str(e))

        logger.info(
            "session_topics_deleted",
            session_id=session_id,
            count=deleted_count,
        )
        return deleted_count
