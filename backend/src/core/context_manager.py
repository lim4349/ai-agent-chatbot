"""Context window management strategies for conversation history."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.core.logging import get_logger
from src.utils.token_counter import (
    count_tokens,
    count_tokens_for_message,
    truncate_messages,
)

if TYPE_CHECKING:
    from src.core.protocols import MemoryStore

logger = get_logger(__name__)


@dataclass
class ContextConfig:
    """Configuration for context management."""

    max_tokens: int = 4000
    """Maximum tokens to keep in context."""

    reserve_tokens: int = 1000
    """Tokens to reserve for response generation."""

    model: str = "gpt-4"
    """Model name for token counting."""

    window_size: int = 10
    """Number of recent messages to keep (for sliding window)."""

    summarization_threshold: int = 3000
    """Token threshold to trigger summarization."""

    recent_messages_to_keep: int = 6
    """Number of recent messages to keep in full (for hybrid strategy)."""


class ContextStrategy(ABC):
    """Abstract base class for context management strategies."""

    def __init__(self, config: ContextConfig | None = None):
        self.config = config or ContextConfig()

    @abstractmethod
    async def manage_context(
        self,
        messages: list[dict],
        store: MemoryStore | None = None,
        session_id: str | None = None,
    ) -> list[dict]:
        """Apply context management strategy to messages.

        Args:
            messages: Full conversation history
            store: Optional memory store for persistence
            session_id: Optional session identifier

        Returns:
            Managed list of messages
        """
        ...

    def _extract_system_message(self, messages: list[dict]) -> tuple[dict | None, list[dict]]:
        """Extract system message from conversation if present.

        Args:
            messages: List of messages

        Returns:
            Tuple of (system_message or None, remaining_messages)
        """
        if messages and messages[0].get("role") == "system":
            return messages[0], messages[1:]
        return None, messages


class SlidingWindowStrategy(ContextStrategy):
    """Sliding window strategy - keeps last N messages."""

    async def manage_context(
        self,
        messages: list[dict],
        store: MemoryStore | None = None,
        session_id: str | None = None,
    ) -> list[dict]:
        """Keep only the last N messages, preserving system message.

        Args:
            messages: Full conversation history
            store: Optional memory store (not used in this strategy)
            session_id: Optional session identifier

        Returns:
            Truncated message list
        """
        if not messages:
            return []

        system_message, remaining = self._extract_system_message(messages)

        # Keep last N messages (or all if fewer)
        window_size = self.config.window_size
        kept_messages = remaining[-window_size:] if len(remaining) > window_size else remaining

        # Add system message back if it exists
        if system_message:
            kept_messages.insert(0, system_message)

        # Verify token count and truncate if needed
        effective_limit = self.config.max_tokens - self.config.reserve_tokens
        result = truncate_messages(
            kept_messages,
            max_tokens=effective_limit,
            model=self.config.model,
            reserve_tokens=0,  # Already accounted for
        )

        logger.debug(
            "sliding_window_applied",
            original_count=len(messages),
            kept_count=len(result),
            window_size=window_size,
        )

        return result


class SummarizationStrategy(ContextStrategy):
    """Summarization strategy - summarizes old messages when threshold exceeded."""

    SUMMARY_MARKER = "[SUMMARY]"

    async def manage_context(
        self,
        messages: list[dict],
        store: MemoryStore | None = None,
        session_id: str | None = None,
    ) -> list[dict]:
        """Summarize old messages when token count exceeds threshold.

        Keeps recent messages raw, older ones summarized.

        Args:
            messages: Full conversation history
            store: Optional memory store for saving/loading summaries
            session_id: Optional session identifier for summary storage

        Returns:
            Managed message list with summary
        """
        if not messages:
            return []

        system_message, remaining = self._extract_system_message(messages)

        # Check current token count
        current_tokens = count_tokens(messages, self.config.model)
        threshold = self.config.summarization_threshold

        if current_tokens <= threshold:
            # No need to summarize yet
            return messages.copy()

        # Calculate how many recent messages to keep
        effective_limit = self.config.max_tokens - self.config.reserve_tokens
        target_summary_tokens = threshold // 3  # Summary should be ~1/3 of threshold

        # Find how many recent messages fit in the remaining budget
        recent_messages = []
        recent_tokens = 0
        split_index = len(remaining)

        for i, msg in enumerate(reversed(remaining)):
            msg_tokens = count_tokens_for_message(msg, self.config.model)
            if recent_tokens + msg_tokens > (effective_limit - target_summary_tokens):
                split_index = len(remaining) - i
                break
            recent_messages.insert(0, msg)
            recent_tokens += msg_tokens

        # Messages to summarize
        to_summarize = remaining[:split_index]

        # Generate or retrieve summary
        summary = await self._get_or_create_summary(
            to_summarize,
            store,
            session_id,
        )

        # Build result
        result = []
        if system_message:
            result.append(system_message)

        if summary:
            summary_message = {
                "role": "system",
                "content": f"{self.SUMMARY_MARKER} Previous conversation summary: {summary}",
            }
            result.append(summary_message)

        result.extend(recent_messages)

        logger.debug(
            "summarization_applied",
            original_count=len(messages),
            summarized_count=len(to_summarize),
            recent_count=len(recent_messages),
            summary_length=len(summary) if summary else 0,
        )

        return result

    async def _get_or_create_summary(
        self,
        messages: list[dict],
        store: MemoryStore | None,
        session_id: str | None,
    ) -> str | None:
        """Get existing summary or create new one.

        Args:
            messages: Messages to summarize
            store: Memory store for persistence
            session_id: Session identifier

        Returns:
            Summary text or None
        """
        # Try to get existing summary from store
        if store and session_id:
            try:
                existing = await store.get_summary(session_id)
                if existing:
                    return existing
            except Exception as e:
                logger.warning("failed_to_get_summary", error=str(e))

        # Generate new summary
        summary = self._generate_summary(messages)

        # Save to store if available
        if store and session_id and summary:
            try:
                await store.add_summary(session_id, summary)
            except Exception as e:
                logger.warning("failed_to_save_summary", error=str(e))

        return summary

    def _generate_summary(self, messages: list[dict]) -> str:
        """Generate a summary of messages.

        This is a simple extraction-based summary. In production,
        this could use an LLM for better summarization.

        Args:
            messages: Messages to summarize

        Returns:
            Summary text
        """
        if not messages:
            return ""

        # Extract key information
        user_messages = [msg.get("content", "") for msg in messages if msg.get("role") == "user"]
        assistant_messages = [
            msg.get("content", "") for msg in messages if msg.get("role") == "assistant"
        ]

        # Create a concise summary
        parts = []

        if user_messages:
            # Take first and last user messages as context
            first_user = user_messages[0][:100]
            parts.append(f"Started with: '{first_user}...'")

            if len(user_messages) > 1:
                last_user = user_messages[-1][:100]
                parts.append(f"Last topic: '{last_user}...'")

        if assistant_messages:
            # Count key actions/tools used
            tool_mentions = sum(
                1
                for msg in assistant_messages
                if any(
                    indicator in msg.lower()
                    for indicator in ["tool", "function", "search", "calculated", "found"]
                )
            )
            if tool_mentions > 0:
                parts.append(f"Used tools {tool_mentions} times")

        summary = " ".join(parts)
        # Limit summary length
        max_summary_len = 500
        if len(summary) > max_summary_len:
            summary = summary[:max_summary_len] + "..."

        return summary


class HybridStrategy(ContextStrategy):
    """Hybrid strategy - keeps last N messages in full, summarizes older ones."""

    SUMMARY_MARKER = "[CONVERSATION SUMMARY]"

    async def manage_context(
        self,
        messages: list[dict],
        store: MemoryStore | None = None,
        session_id: str | None = None,
    ) -> list[dict]:
        """Keep last N messages in full, summarize older messages.

        This is the recommended strategy that balances context
        preservation with token efficiency.

        Args:
            messages: Full conversation history
            store: Optional memory store for saving/loading summaries
            session_id: Optional session identifier

        Returns:
            Managed message list with summary and recent messages
        """
        if not messages:
            return []

        system_message, remaining = self._extract_system_message(messages)

        # If we have fewer messages than the threshold, keep all
        recent_to_keep = self.config.recent_messages_to_keep
        if len(remaining) <= recent_to_keep:
            result = []
            if system_message:
                result.append(system_message)
            result.extend(remaining)
            return result

        # Split into recent (keep full) and old (summarize)
        recent_messages = remaining[-recent_to_keep:]
        old_messages = remaining[:-recent_to_keep]

        # Get or create summary of old messages
        summary = await self._get_or_create_summary(
            old_messages,
            store,
            session_id,
        )

        # Build result
        result = []
        if system_message:
            result.append(system_message)

        if summary:
            summary_message = {
                "role": "system",
                "content": f"{self.SUMMARY_MARKER} {summary}",
            }
            result.append(summary_message)

        result.extend(recent_messages)

        # Verify we're within token limits
        effective_limit = self.config.max_tokens - self.config.reserve_tokens
        final_tokens = count_tokens(result, self.config.model)

        if final_tokens > effective_limit:
            # Fall back to truncation if still over limit
            result = truncate_messages(
                result,
                max_tokens=effective_limit,
                model=self.config.model,
                reserve_tokens=0,
            )

        logger.debug(
            "hybrid_strategy_applied",
            original_count=len(messages),
            old_count=len(old_messages),
            recent_count=len(recent_messages),
            summary_present=bool(summary),
            final_token_count=count_tokens(result, self.config.model),
        )

        return result

    async def _get_or_create_summary(
        self,
        messages: list[dict],
        store: MemoryStore | None,
        session_id: str | None,
    ) -> str | None:
        """Get existing summary or create new one.

        Args:
            messages: Messages to summarize
            store: Memory store for persistence
            session_id: Session identifier

        Returns:
            Summary text or None
        """
        # Try to get existing summary from store
        if store and session_id:
            try:
                existing = await store.get_summary(session_id)
                if existing:
                    # Append new messages to existing summary
                    new_summary = self._update_summary(existing, messages)
                    await store.add_summary(session_id, new_summary)
                    return new_summary
            except Exception as e:
                logger.warning("failed_to_get_summary", error=str(e))

        # Generate new summary
        return self._generate_summary(messages)

    def _update_summary(self, existing_summary: str, new_messages: list[dict]) -> str:
        """Update existing summary with new messages.

        Args:
            existing_summary: Current summary
            new_messages: New messages to incorporate

        Returns:
            Updated summary
        """
        new_summary = self._generate_summary(new_messages)
        if not new_summary:
            return existing_summary

        combined = f"{existing_summary} | Then: {new_summary}"
        max_len = 800
        if len(combined) > max_len:
            combined = combined[:max_len] + "..."

        return combined

    def _generate_summary(self, messages: list[dict]) -> str:
        """Generate a summary of messages.

        Args:
            messages: Messages to summarize

        Returns:
            Summary text
        """
        if not messages:
            return ""

        # Extract topics from user messages
        topics = []
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")[:80]
                if content:
                    topics.append(content)

        # Extract key responses
        key_points = []
        for msg in messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                # Look for structured responses
                if any(marker in content for marker in ["1.", "2.", "- ", "* "]):
                    key_points.append("provided structured response")
                    break

        # Build summary
        parts = []

        if topics:
            if len(topics) == 1:
                parts.append(f"Discussed: {topics[0]}...")
            else:
                parts.append(
                    f"Topics: {', '.join(t[:40] + '...' if len(t) > 40 else t for t in topics[:2])}"
                )

        if key_points:
            parts.append(f"({'; '.join(key_points)})")

        summary = " ".join(parts)
        max_summary_len = 600
        if len(summary) > max_summary_len:
            summary = summary[:max_summary_len] + "..."

        return summary


class ContextManager:
    """Manages conversation context using configurable strategies."""

    def __init__(
        self,
        strategy: ContextStrategy | None = None,
        store: MemoryStore | None = None,
    ):
        """Initialize context manager.

        Args:
            strategy: Context management strategy (defaults to HybridStrategy)
            store: Optional memory store for persistence
        """
        self.strategy = strategy or HybridStrategy()
        self.store = store

    async def prepare_context(
        self,
        messages: list[dict],
        session_id: str | None = None,
    ) -> list[dict]:
        """Prepare context for LLM call.

        Args:
            messages: Full conversation history
            session_id: Optional session identifier

        Returns:
            Managed message list ready for LLM
        """
        return await self.strategy.manage_context(messages, self.store, session_id)

    def set_strategy(self, strategy: ContextStrategy) -> None:
        """Change the context management strategy.

        Args:
            strategy: New strategy to use
        """
        self.strategy = strategy
        logger.info("context_strategy_changed", strategy_type=type(strategy).__name__)

    def get_token_count(self, messages: list[dict]) -> int:
        """Get token count for messages.

        Args:
            messages: List of messages

        Returns:
            Token count
        """
        return count_tokens(messages, self.strategy.config.model)


# Factory function for easy strategy selection
def create_context_manager(
    strategy_type: str = "hybrid",
    config: ContextConfig | None = None,
    store: MemoryStore | None = None,
) -> ContextManager:
    """Create a context manager with specified strategy.

    Args:
        strategy_type: One of "sliding_window", "summarization", "hybrid"
        config: Optional configuration
        store: Optional memory store

    Returns:
        Configured ContextManager
    """
    strategies = {
        "sliding_window": SlidingWindowStrategy,
        "summarization": SummarizationStrategy,
        "hybrid": HybridStrategy,
    }

    strategy_class = strategies.get(strategy_type.lower(), HybridStrategy)
    strategy = strategy_class(config)

    return ContextManager(strategy, store)
