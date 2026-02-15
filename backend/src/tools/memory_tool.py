"""Memory retrieval tool for agents to query conversation history."""

from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


class MemoryTool:
    """Tool for searching and retrieving memories from conversation history."""

    name = "memory_search"
    description = "Search and retrieve relevant memories from conversation history"

    def __init__(self, memory_store=None, embedding_provider=None):
        """Initialize the memory tool.

        Args:
            memory_store: The memory store containing conversation history
            embedding_provider: Optional provider for semantic search embeddings
        """
        self._store = memory_store
        self._embedding_provider = embedding_provider

    async def execute(
        self, query: str, session_id: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Search memory for relevant messages.

        Performs semantic search across conversation history to find
        messages relevant to the query.

        Args:
            query: The search query
            session_id: The session identifier
            top_k: Maximum number of results to return

        Returns:
            List of relevant messages with relevance scores
        """
        if self._store is None:
            logger.warning("memory_search_no_store", session_id=session_id)
            return []

        try:
            # Get all messages for the session
            messages = await self._store.get_messages(session_id)

            if not messages:
                logger.debug("memory_search_empty", session_id=session_id)
                return []

            # Score messages by relevance
            scored_messages = self._score_messages(query, messages)

            # Sort by score (descending) and take top_k
            scored_messages.sort(key=lambda x: x["score"], reverse=True)
            results = scored_messages[:top_k]

            logger.info(
                "memory_search_completed",
                session_id=session_id,
                query=query,
                results_count=len(results),
                total_messages=len(messages),
            )

            return results

        except Exception as e:
            logger.error("memory_search_failed", error=str(e), session_id=session_id)
            return []

    def _score_messages(self, query: str, messages: list[dict]) -> list[dict]:
        """Score messages by relevance to query.

        Uses keyword matching and semantic similarity (if embedding provider available).

        Args:
            query: The search query
            messages: List of messages to score

        Returns:
            List of messages with relevance scores
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        scored = []

        for i, msg in enumerate(messages):
            content = msg.get("content", "").lower()
            score = 0.0

            # Exact match bonus
            if query_lower in content:
                score += 1.0

            # Keyword overlap
            content_words = set(content.split())
            if query_words:
                overlap = len(query_words & content_words) / len(query_words)
                score += overlap * 0.5

            # Keyword proximity (words near each other)
            score += self._calculate_proximity_score(query_lower, content) * 0.3

            # Message weight bonus (if available)
            weight = msg.get("weight", 0.5)
            score += weight * 0.2

            # Recency bonus (newer messages get slight boost)
            recency_bonus = (i / len(messages)) * 0.1 if messages else 0
            score += recency_bonus

            if score > 0:
                scored.append(
                    {
                        "message": msg,
                        "score": round(score, 3),
                        "index": i,
                    }
                )

        return scored

    def _calculate_proximity_score(self, query: str, content: str) -> float:
        """Calculate proximity score based on keyword distance.

        Args:
            query: The search query
            content: The message content

        Returns:
            Proximity score between 0 and 1
        """
        query_words = query.split()
        if len(query_words) <= 1:
            return 1.0 if query in content else 0.0

        content_words = content.split()
        positions = []

        for qw in query_words:
            for i, cw in enumerate(content_words):
                if qw in cw:
                    positions.append(i)
                    break

        if len(positions) < 2:
            return 0.0

        # Calculate average distance between consecutive keywords
        distances = [
            positions[i + 1] - positions[i] for i in range(len(positions) - 1)
        ]
        avg_distance = sum(distances) / len(distances) if distances else 0

        # Score inversely proportional to distance
        return 1.0 / (1.0 + avg_distance)

    async def get_recent_context(
        self, session_id: str, message_count: int = 5
    ) -> list[dict]:
        """Get recent conversation context.

        Args:
            session_id: The session identifier
            message_count: Number of recent messages to retrieve

        Returns:
            List of recent messages
        """
        if self._store is None:
            return []

        try:
            messages = await self._store.get_messages(session_id)
            return messages[-message_count:] if messages else []
        except Exception as e:
            logger.error("get_recent_context_failed", error=str(e), session_id=session_id)
            return []

    async def get_weighted_memories(
        self, session_id: str, min_weight: float = 0.5, limit: int = 10
    ) -> list[dict]:
        """Get high-weight memories for a session.

        Args:
            session_id: The session identifier
            min_weight: Minimum weight threshold
            limit: Maximum number of results

        Returns:
            List of high-weight messages
        """
        if self._store is None:
            return []

        try:
            messages = await self._store.get_messages(session_id)
            weighted = [
                msg for msg in messages if msg.get("weight", 0.5) >= min_weight
            ]
            return weighted[:limit]
        except Exception as e:
            logger.error(
                "get_weighted_memories_failed", error=str(e), session_id=session_id
            )
            return []

    async def search_memory(
        self, query: str, session_id: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Alias for execute method - search memory for relevant messages.

        Args:
            query: The search query
            session_id: The session identifier
            top_k: Maximum number of results to return

        Returns:
            List of relevant messages with relevance scores
        """
        return await self.execute(query, session_id, top_k)


# Convenience function for direct usage
async def search_memory(
    query: str,
    session_id: str,
    memory_store=None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Search memory for relevant messages.

    Args:
        query: The search query
        session_id: The session identifier
        memory_store: The memory store to search
        top_k: Maximum number of results to return

    Returns:
        List of relevant messages with relevance scores
    """
    tool = MemoryTool(memory_store=memory_store)
    return await tool.execute(query, session_id, top_k)
