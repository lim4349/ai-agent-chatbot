"""Memory weight system for assigning importance scores to messages."""

import re
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


class MemoryWeightSystem:
    """Assigns and manages importance weights for messages in memory."""

    # Weight thresholds
    HIGH_WEIGHT = 0.8
    MEDIUM_WEIGHT = 0.5
    LOW_WEIGHT = 0.0

    # Factors for weight calculation
    LENGTH_FACTOR = 0.1  # Weight per 100 characters (max 0.3)
    CODE_FACTOR = 0.2  # Bonus for containing code
    QUESTION_FACTOR = 0.15  # Bonus for questions
    EMPHASIS_FACTOR = 0.15  # Bonus for user emphasis

    def __init__(self, memory_store=None):
        """Initialize with optional memory store.

        Args:
            memory_store: The memory store to use for persisting weights
        """
        self._store = memory_store

    def calculate_message_weight(self, message: dict[str, Any]) -> float:
        """Calculate importance weight for a message.

        Factors:
        - Message length (longer messages often contain more info)
        - Contains code blocks (code is valuable)
        - Contains questions (indicates user needs)
        - User emphasis (exclamation marks, capitalization, etc.)

        Args:
            message: The message dictionary with 'content' and 'role' keys

        Returns:
            Float weight between 0.0 and 1.0
        """
        content = message.get("content", "")
        weight = 0.0

        # Length factor (capped at 0.3 for very long messages)
        length_score = min(len(content) / 1000, 0.3)
        weight += length_score

        # Code detection
        if self._contains_code(content):
            weight += self.CODE_FACTOR

        # Question detection
        if self._contains_question(content):
            weight += self.QUESTION_FACTOR

        # User emphasis detection
        if self._contains_emphasis(content):
            weight += self.EMPHASIS_FACTOR

        # Cap at 1.0
        final_weight = min(round(weight, 2), 1.0)

        logger.debug(
            "weight_calculated",
            role=message.get("role"),
            weight=final_weight,
            content_length=len(content),
        )

        return final_weight

    def _contains_code(self, content: str) -> bool:
        """Check if content contains code blocks or code-like patterns."""
        # Check for code blocks
        if "```" in content:
            return True

        # Check for inline code
        if "`" in content:
            return True

        # Check for common code patterns
        code_patterns = [
            r"def\s+\w+\s*\(",  # Python function
            r"class\s+\w+",  # Python class
            r"function\s+\w+\s*\(",  # JavaScript function
            r"const\s+\w+\s*[=:]",  # Variable declaration
            r"import\s+\w+",  # Import statement
            r"from\s+\w+\s+import",  # Python import
            r"console\.log\s*\(",  # Console log
            r"print\s*\(",  # Print statement
        ]

        for pattern in code_patterns:
            if re.search(pattern, content):
                return True

        return False

    def _contains_question(self, content: str) -> bool:
        """Check if content contains questions."""
        # Korean question marks
        if "?" in content or "？" in content:
            return True

        # Korean question words
        question_words = [
            "어떻게",
            "무엇",
            "뭐",
            "왜",
            "언제",
            "어디",
            "누구",
            "몇",
            "얼마",
            "있나요",
            "있니",
            "해줘",
            "알려줘",
        ]

        content_lower = content.lower()
        for word in question_words:
            if word in content_lower:
                return True

        return False

    def _contains_emphasis(self, content: str) -> bool:
        """Check if content contains user emphasis markers."""
        # Multiple exclamation marks
        if "!!" in content:
            return True

        # Multiple question marks
        if "??" in content:
            return True

        # ALL CAPS words (at least 3 characters)
        words = content.split()
        for word in words:
            clean_word = re.sub(r"[^\w]", "", word)
            if len(clean_word) >= 3 and clean_word.isupper():
                return True

        # Emphasis markers
        emphasis_markers = ["정말", "매우", "굉장히", "꼭", "반드시", "반드시", "중요"]
        content_lower = content.lower()
        for marker in emphasis_markers:
            if marker in content_lower:
                return True

        return False

    async def update_message_weight(
        self, session_id: str, message_id: str, weight: float
    ) -> None:
        """Update the weight of a specific message.

        Args:
            session_id: The session identifier
            message_id: The message identifier (index or ID)
            weight: The new weight value (0.0 to 1.0)
        """
        if self._store is None:
            logger.warning("update_weight_no_store", session_id=session_id)
            return

        # Clamp weight to valid range
        weight = max(0.0, min(1.0, weight))

        try:
            messages = await self._store.get_messages(session_id)

            # Find message by ID or index
            for i, msg in enumerate(messages):
                if str(i) == message_id or msg.get("id") == message_id:
                    msg["weight"] = weight
                    # Update in store (this depends on store implementation)
                    if hasattr(self._store, "update_message"):
                        await self._store.update_message(session_id, i, msg)
                    logger.info(
                        "weight_updated",
                        session_id=session_id,
                        message_id=message_id,
                        weight=weight,
                    )
                    break
        except Exception as e:
            logger.error("weight_update_failed", error=str(e), session_id=session_id)

    async def get_weighted_messages(
        self, session_id: str, min_weight: float = 0.5
    ) -> list[dict]:
        """Get messages filtered by minimum weight.

        Args:
            session_id: The session identifier
            min_weight: Minimum weight threshold (default 0.5)

        Returns:
            List of messages with weight >= min_weight
        """
        if self._store is None:
            logger.warning("get_weighted_no_store", session_id=session_id)
            return []

        try:
            messages = await self._store.get_messages(session_id)

            # Filter by weight (assign weight if not present)
            weighted_messages = []
            for msg in messages:
                weight = msg.get("weight")
                if weight is None:
                    weight = self.calculate_message_weight(msg)
                    msg["weight"] = weight

                if weight >= min_weight:
                    weighted_messages.append(msg)

            logger.debug(
                "weighted_messages_filtered",
                session_id=session_id,
                total=len(messages),
                filtered=len(weighted_messages),
                min_weight=min_weight,
            )

            return weighted_messages

        except Exception as e:
            logger.error("get_weighted_failed", error=str(e), session_id=session_id)
            return []

    async def store_message_with_weight(
        self, session_id: str, message: dict[str, Any]
    ) -> dict[str, Any]:
        """Calculate and store weight with a message.

        Args:
            session_id: The session identifier
            message: The message to store

        Returns:
            The message with weight added
        """
        weight = self.calculate_message_weight(message)
        message["weight"] = weight

        if self._store:
            await self._store.add_message(session_id, message)

        return message


def calculate_message_weight(message: dict[str, Any]) -> float:
    """Standalone function to calculate message weight.

    Args:
        message: The message dictionary

    Returns:
        Float weight between 0.0 and 1.0
    """
    system = MemoryWeightSystem()
    return system.calculate_message_weight(message)
