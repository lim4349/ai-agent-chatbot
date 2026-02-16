"""Topic memory for tracking conversation topics across sessions."""

from datetime import datetime
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

    _TOPIC_EXTRACTION_PROMPT = """Analyze the following conversation and extract the main topics discussed.

Conversation:
{conversation}

Extract 1-5 main topics from this conversation. For each topic:
1. Provide a concise topic name (2-4 words)
2. Write a brief summary (1-2 sentences)
3. Assess the relevance/importance (0.0-1.0)

Respond in JSON format:
{
    "topics": [
        {
            "topic": "topic name",
            "summary": "brief summary",
            "relevance": 0.8
        }
    ]
}

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
            result = await self.llm.generate_structured(
                messages=[
                    {
                        "role": "user",
                        "content": self._TOPIC_EXTRACTION_PROMPT.format(conversation=conversation),
                    }
                ],
                output_schema=dict,
            )

            topics = result.get("topics", [])

            # Sort by relevance
            topics.sort(key=lambda x: x.get("relevance", 0), reverse=True)

            logger.debug("topics_extracted", topic_count=len(topics))
            return topics

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
                    "added_at": datetime.utcnow().isoformat(),
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

        # Store each topic
        for topic_data in topics:
            topic_name = topic_data.get("topic")
            if not topic_name:
                continue

            # Generate detailed summary
            summary = await self.generate_topic_summary(topic_name, messages)

            # Store in long-term memory
            await self.add_session_to_topic(
                session_id=session_id,
                topic=topic_name,
                summary=summary or topic_data.get("summary", ""),
            )

        logger.debug(
            "session_topics_processed",
            session_id=session_id,
            topic_count=len(topics),
        )

        return topics

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
        """Get cross-session context based on topic similarity.

        Args:
            session_id: Current session ID
            messages: Recent conversation messages

        Returns:
            Context string with related session information
        """
        if not messages:
            return ""

        # Extract current topics
        current_topics = await self.extract_topics(messages[-5:])

        if not current_topics:
            return ""

        context_parts = []

        # Get related sessions
        related_sessions = await self.get_related_sessions(session_id)

        if related_sessions:
            context_parts.append(
                f"This topic has been discussed in {len(related_sessions)} previous conversation(s)."
            )

        # Get context for top topic
        top_topic = current_topics[0].get("topic")
        if top_topic:
            topic_context = await self.get_context_for_topic(top_topic, session_id)
            if topic_context:
                context_parts.append(topic_context)

        if not context_parts:
            return ""

        return "\n\n".join(context_parts)
