"""Topic memory for tracking conversation topics across sessions."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.core.logging import get_logger

if TYPE_CHECKING:
    from src.memory.long_term_memory import LongTermMemory

logger = get_logger(__name__)


class TopicMemory:
    """Track conversation topics and link related sessions.

    Extracts main topics from conversations, stores topic summaries,
    and maintains relationships between sessions by topic.
    """

    def __init__(
        self,
        llm,
        long_term_memory: "LongTermMemory | None" = None,
    ):
        """Initialize topic memory.

        Args:
            llm: LLM provider for topic extraction
            long_term_memory: Long-term memory store for persistence
        """
        self.llm = llm
        self.memory = long_term_memory
        self._min_relevance = 0.7
        self._max_topics_per_pass = 3

    _TOPIC_EXTRACTION_PROMPT = """Analyze the following conversation and extract the main topics discussed.

Conversation:
{conversation}

Extract 1-5 main topics from this conversation. For each topic:
1. Provide a concise topic name (2-4 words)
2. Write a brief summary (1-2 sentences)
3. Assess the relevance/importance (0.0-1.0)

Respond in JSON format:
{{
    "topics": [
        {{
            "topic": "topic name",
            "summary": "brief, generalized summary without names, emails, companies, repos, URLs, ticket IDs, or secrets",
            "relevance": 0.8
        }}
    ]
}}

Do not include personal identifiers, company/customer names, repository names, URLs, issue keys, or secrets.
Respond with valid JSON only."""

    _SUMMARY_GENERATION_PROMPT = """Summarize the following conversation about the topic "{topic}".

Conversation:
{conversation}

Create a concise summary (2-3 sentences) that captures:
- Key points discussed about {topic}
- Any decisions or conclusions reached
- Open questions or next steps

Summary:"""

    async def extract_topics(self, messages: list[dict]) -> list[dict]:
        """Extract main topics from a conversation.

        Args:
            messages: List of conversation messages

        Returns:
            List of topic dictionaries with topic, summary, and relevance
        """
        if not messages:
            return []

        conversation = self._format_conversation(messages)

        try:
            # Use JSON mode instead of structured output for better compatibility
            prompt = self._TOPIC_EXTRACTION_PROMPT.format(conversation=conversation)
            result_text, _ = await self.llm.generate_with_usage(
                [
                    {
                        "role": "system",
                        "content": 'Respond with valid JSON only. Format: {"topics": [{"topic": "...", "summary": "...", "relevance": 0.8}]}',
                    },
                    {"role": "user", "content": prompt},
                ]
            )

            # Parse JSON response
            import json

            try:
                result = json.loads(result_text)
            except json.JSONDecodeError:
                logger.warning("topic_extraction_json_parse_failed")
                return []

            if not result:
                logger.warning("topic_extraction_empty_result")
                return []

            topics = result.get("topics", [])

            # Handle different response formats from LLM
            normalized_topics = []
            for item in topics:
                if isinstance(item, dict):
                    # Expected format: {"topic": "...", "summary": "...", "relevance": 0.8}
                    normalized_topics.append(item)
                elif isinstance(item, str):
                    # Fallback format: just topic name as string
                    normalized_topics.append({"topic": item, "summary": item, "relevance": 0.5})

            # Sort by relevance
            normalized_topics.sort(key=lambda x: x.get("relevance", 0), reverse=True)

            logger.debug("topics_extracted", topic_count=len(normalized_topics))
            return normalized_topics

        except Exception as e:
            logger.error("topic_extraction_failed", error=str(e))
            return []

    async def add_session_to_topic(
        self,
        session_id: str,
        topic: str,
        summary: str | None = None,
    ) -> None:
        """Associate a session with a topic.

        Args:
            session_id: Session identifier
            topic: Topic name
            summary: Optional topic summary
        """
        if not self.memory:
            return

        try:
            await self.memory.store_topic_summary(
                topic=topic,
                summary=summary or f"Session: {session_id}",
                session_id=session_id,
                metadata={
                    "added_at": datetime.now(tz=UTC).isoformat(),
                },
            )

            logger.debug(
                "session_added_to_topic",
                session_id=session_id,
                topic=topic,
            )

        except Exception as e:
            logger.error("failed_to_add_session", error=str(e))

    async def get_topic_history(
        self,
        topic: str,
        limit: int = 10,
    ) -> list[dict]:
        """Get history of sessions and summaries for a topic.

        Args:
            topic: Topic name
            limit: Maximum number of entries to return

        Returns:
            List of topic history entries
        """
        if not self.memory:
            return []

        try:
            return await self.memory.get_topic_history(topic, limit)

        except Exception as e:
            logger.error("topic_history_failed", error=str(e))
            return []

    async def find_related_topics(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Find topics related to a query.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of related topic summaries
        """
        if not self.memory:
            return []

        try:
            return await self.memory.search_topics(query, top_k)

        except Exception as e:
            logger.error("related_topics_search_failed", error=str(e))
            return []

    async def get_related_sessions(self, session_id: str) -> list[str]:
        """Get sessions related to the given session by topic.

        Args:
            session_id: Session identifier

        Returns:
            List of related session IDs
        """
        if not self.memory:
            return []

        try:
            return await self.memory.get_related_sessions(session_id)

        except Exception as e:
            logger.error("related_sessions_failed", error=str(e))
            return []

    async def generate_topic_summary(
        self,
        topic: str,
        messages: list[dict],
    ) -> str | None:
        """Generate a summary for a specific topic from conversation.

        Args:
            topic: Topic name
            messages: Conversation messages

        Returns:
            Generated summary or None if failed
        """
        if not messages:
            return None

        conversation = self._format_conversation(messages)

        try:
            summary = await self.llm.generate(
                messages=[
                    {
                        "role": "user",
                        "content": self._SUMMARY_GENERATION_PROMPT.format(
                            topic=topic,
                            conversation=conversation,
                        ),
                    }
                ],
            )

            return summary.strip()

        except Exception as e:
            logger.error("summary_generation_failed", error=str(e))
            return None

    async def process_session_topics(
        self,
        session_id: str,
        messages: list[dict],
    ) -> list[dict]:
        """Extract and store topics for a session.

        Args:
            session_id: Session identifier
            messages: Conversation messages

        Returns:
            List of extracted topics
        """
        # Extract topics
        topics = await self.extract_topics(messages)

        filtered_topics = [
            topic
            for topic in topics
            if topic.get("topic") and topic.get("relevance", 0) >= self._min_relevance
        ]

        # Store only the top few high-signal topics
        for topic_data in filtered_topics[: self._max_topics_per_pass]:
            topic_name = topic_data.get("topic")
            summary = (topic_data.get("summary") or "").strip()
            if len(summary) < 24:
                summary = await self.generate_topic_summary(topic_name, messages) or ""

            # Store in long-term memory
            await self.add_session_to_topic(
                session_id=session_id,
                topic=topic_name,
                summary=summary,
            )

        logger.debug(
            "session_topics_processed",
            session_id=session_id,
            topic_count=len(filtered_topics[: self._max_topics_per_pass]),
        )

        return filtered_topics[: self._max_topics_per_pass]

    def _format_conversation(self, messages: list[dict]) -> str:
        """Format messages for analysis.

        Args:
            messages: List of conversation messages

        Returns:
            Formatted conversation string
        """
        lines = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    async def get_context_for_topic(
        self,
        topic: str,
        current_session_id: str | None = None,
    ) -> str:
        """Get contextual information about a topic for injection into prompts.

        Args:
            topic: Topic name
            current_session_id: Current session to exclude from history

        Returns:
            Context string for prompt injection
        """
        history = await self.get_topic_history(topic, limit=3)

        if not history:
            return ""

        context_parts = [f"Previous discussions about '{topic}':"]

        for entry in history:
            session_id = entry.get("session_id")
            if session_id == current_session_id:
                continue

            summary = entry.get("summary", "")
            if summary:
                context_parts.append(f"- {summary}")

        if len(context_parts) == 1:
            return ""

        return "\n".join(context_parts)

    async def get_cross_session_context(
        self,
        session_id: str,
        messages: list[dict],
    ) -> str:
        """Get cross-session context using stored topic names (no LLM call).

        Topics are populated by _process_topics() after every 5 messages.
        Returns empty string for new sessions with no stored topics yet.
        """
        if not self.memory:
            return ""

        # Use stored topic names — avoids LLM call inside the streaming node
        stored_topics = await self.memory.get_session_topic_names(session_id)
        if not stored_topics:
            return ""

        context_parts = []

        related_sessions = await self.get_related_sessions(session_id)
        if related_sessions:
            context_parts.append(
                f"This topic has been discussed in {len(related_sessions)} previous conversation(s)."
            )

        top_topic = next(iter(stored_topics))
        topic_context = await self.get_context_for_topic(top_topic, session_id)
        if topic_context:
            context_parts.append(topic_context)

        if not context_parts:
            return ""

        return "\n\n".join(context_parts)
