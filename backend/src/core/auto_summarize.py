"""Auto-summarization trigger for conversation management."""

from datetime import datetime, timedelta
from typing import Any, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class AutoSummarizeTrigger:
    """Triggers summarization based on conversation thresholds."""

    # Default thresholds
    DEFAULT_TOKEN_THRESHOLD = 2000  # Approximate tokens
    DEFAULT_MESSAGE_THRESHOLD = 20  # Number of messages
    DEFAULT_TIME_THRESHOLD_MINUTES = 10  # Minutes since last summary

    def __init__(
        self,
        token_threshold: int = DEFAULT_TOKEN_THRESHOLD,
        message_threshold: int = DEFAULT_MESSAGE_THRESHOLD,
        time_threshold_minutes: int = DEFAULT_TIME_THRESHOLD_MINUTES,
        memory_store=None,
    ):
        """Initialize the auto-summarization trigger.

        Args:
            token_threshold: Token count threshold for triggering summarization
            message_threshold: Message count threshold for triggering summarization
            time_threshold_minutes: Time since last summary threshold
            memory_store: Optional memory store for tracking summaries
        """
        self.token_threshold = token_threshold
        self.message_threshold = message_threshold
        self.time_threshold = timedelta(minutes=time_threshold_minutes)
        self._store = memory_store
        # Track last summary time per session
        self._last_summary_times: dict[str, datetime] = {}

    def _estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Estimate token count from messages.

        Uses a rough approximation: ~4 characters per token.

        Args:
            messages: List of message dictionaries

        Returns:
            Estimated token count
        """
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        # Rough estimate: 4 characters per token
        return total_chars // 4

    def _get_last_summary_time(self, session_id: str) -> Optional[datetime]:
        """Get the last summary time for a session.

        Args:
            session_id: The session identifier

        Returns:
            Last summary datetime or None if never summarized
        """
        return self._last_summary_times.get(session_id)

    def _update_last_summary_time(self, session_id: str) -> None:
        """Update the last summary time for a session.

        Args:
            session_id: The session identifier
        """
        self._last_summary_times[session_id] = datetime.now()
        logger.info("summary_time_updated", session_id=session_id)

    async def should_summarize(self, session_id: str, messages: list[dict[str, Any]]) -> bool:
        """Check if summarization should be triggered.

        Checks:
        - Token count exceeds threshold
        - Message count exceeds threshold
        - Time since last summary exceeds threshold

        Args:
            session_id: The session identifier
            messages: Current conversation messages

        Returns:
            True if summarization should be triggered
        """
        if not messages:
            return False

        # Check token count
        estimated_tokens = self._estimate_tokens(messages)
        if estimated_tokens >= self.token_threshold:
            logger.info(
                "summarize_token_threshold",
                session_id=session_id,
                tokens=estimated_tokens,
                threshold=self.token_threshold,
            )
            return True

        # Check message count
        if len(messages) >= self.message_threshold:
            logger.info(
                "summarize_message_threshold",
                session_id=session_id,
                messages=len(messages),
                threshold=self.message_threshold,
            )
            return True

        # Check time since last summary
        last_summary = self._get_last_summary_time(session_id)
        if last_summary:
            time_since = datetime.now() - last_summary
            if time_since >= self.time_threshold:
                logger.info(
                    "summarize_time_threshold",
                    session_id=session_id,
                    minutes=time_since.total_seconds() / 60,
                    threshold=self.time_threshold.total_seconds() / 60,
                )
                return True

        logger.debug(
            "summarize_not_needed",
            session_id=session_id,
            tokens=estimated_tokens,
            messages=len(messages),
        )
        return False

    async def trigger_summarization(self, session_id: str) -> str:
        """Trigger the summarization process.

        This method should be called when should_summarize returns True.
        It updates tracking state and returns a status message.

        Args:
            session_id: The session identifier

        Returns:
            Status message indicating summarization was triggered
        """
        self._update_last_summary_time(session_id)

        logger.info("summarization_triggered", session_id=session_id)

        return f"Summarization triggered for session {session_id}"

    async def get_summary_status(self, session_id: str) -> dict[str, Any]:
        """Get the current summarization status for a session.

        Args:
            session_id: The session identifier

        Returns:
            Dictionary with status information
        """
        last_summary = self._get_last_summary_time(session_id)
        time_since = None

        if last_summary:
            time_since_minutes = (datetime.now() - last_summary).total_seconds() / 60
            time_since = round(time_since_minutes, 1)

        return {
            "session_id": session_id,
            "last_summary": last_summary.isoformat() if last_summary else None,
            "time_since_minutes": time_since,
            "thresholds": {
                "token_threshold": self.token_threshold,
                "message_threshold": self.message_threshold,
                "time_threshold_minutes": self.time_threshold.total_seconds() / 60,
            },
        }

    def reset_session(self, session_id: str) -> None:
        """Reset the summary tracking for a session.

        Args:
            session_id: The session identifier
        """
        self._last_summary_times.pop(session_id, None)
        logger.info("session_summary_reset", session_id=session_id)


class SummarizationManager:
    """Manages conversation summarization with configurable strategies."""

    def __init__(
        self,
        llm=None,
        memory_store=None,
        token_threshold: int = 2000,
        message_threshold: int = 20,
        time_threshold_minutes: int = 10,
    ):
        """Initialize the summarization manager.

        Args:
            llm: LLM instance for generating summaries
            memory_store: Memory store for persisting summaries
            token_threshold: Token count threshold
            message_threshold: Message count threshold
            time_threshold_minutes: Time threshold in minutes
        """
        self.llm = llm
        self._store = memory_store
        self.trigger = AutoSummarizeTrigger(
            token_threshold=token_threshold,
            message_threshold=message_threshold,
            time_threshold_minutes=time_threshold_minutes,
            memory_store=memory_store,
        )

    async def check_and_summarize(
        self, session_id: str, messages: list[dict[str, Any]]
    ) -> Optional[dict[str, Any]]:
        """Check if summarization is needed and perform it.

        Args:
            session_id: The session identifier
            messages: Current conversation messages

        Returns:
            Summary result dictionary or None if not triggered
        """
        if not await self.trigger.should_summarize(session_id, messages):
            return None

        if self.llm is None:
            logger.warning("summarize_no_llm", session_id=session_id)
            return None

        try:
            # Generate summary
            summary = await self._generate_summary(messages)

            # Store summary if memory store available
            if self._store:
                await self._store_summary(session_id, summary, messages)

            # Update trigger state
            await self.trigger.trigger_summarization(session_id)

            return {
                "session_id": session_id,
                "summary": summary,
                "messages_summarized": len(messages),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error("summarization_failed", error=str(e), session_id=session_id)
            return None

    async def _generate_summary(self, messages: list[dict[str, Any]]) -> str:
        """Generate a summary of the conversation.

        Args:
            messages: Messages to summarize

        Returns:
            Generated summary text
        """
        # Build conversation text
        conversation = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            conversation.append(f"{role}: {content}")

        conversation_text = "\n".join(conversation)

        # Create summary prompt
        summary_prompt = f"""Please provide a concise summary of the following conversation.
Focus on key points, decisions, and important information shared.

Conversation:
{conversation_text}

Summary:"""

        # Generate summary using LLM
        response = await self.llm.generate(
            [{"role": "user", "content": summary_prompt}]
        )

        return response if isinstance(response, str) else response.get("content", "")

    async def _store_summary(
        self, session_id: str, summary: str, messages: list[dict[str, Any]]
    ) -> None:
        """Store the summary in memory.

        Args:
            session_id: The session identifier
            summary: The generated summary
            messages: The messages that were summarized
        """
        summary_message = {
            "role": "system",
            "content": f"[Summary of previous conversation]: {summary}",
            "type": "summary",
            "messages_count": len(messages),
            "timestamp": datetime.now().isoformat(),
        }

        await self._store.add_message(session_id, summary_message)
        logger.info("summary_stored", session_id=session_id, messages_count=len(messages))

    async def get_conversation_summary(self, session_id: str) -> Optional[str]:
        """Get the latest summary for a session.

        Args:
            session_id: The session identifier

        Returns:
            Latest summary or None if not found
        """
        if not self._store:
            return None

        try:
            messages = await self._store.get_messages(session_id)
            for msg in reversed(messages):
                if msg.get("type") == "summary":
                    return msg.get("content")
            return None
        except Exception as e:
            logger.error("get_summary_failed", error=str(e), session_id=session_id)
            return None
