"""Token counting utility using tiktoken."""

from __future__ import annotations

import tiktoken

from src.core.logging import get_logger

logger = get_logger(__name__)

# Token limits per model (context window sizes)
MODEL_TOKEN_LIMITS = {
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-3.5-turbo": 16385,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "claude-3-5-sonnet": 200000,
    "claude": 100000,  # Generic fallback
}

# Default tokens to reserve for response generation
DEFAULT_RESPONSE_RESERVE = 1000


def get_encoding_for_model(model: str) -> tiktoken.Encoding:
    """Get the appropriate tokenizer encoding for a model.

    Args:
        model: Model name (e.g., "gpt-4", "claude-3-opus")

    Returns:
        tiktoken Encoding instance
    """
    model_lower = model.lower()

    # OpenAI models - use cl100k_base
    if any(m in model_lower for m in ["gpt-4", "gpt-3.5"]):
        try:
            return tiktoken.encoding_for_model(model_lower)
        except KeyError:
            # Fallback to cl100k_base for unknown OpenAI models
            return tiktoken.get_encoding("cl100k_base")

    # Anthropic models - approximate with cl100k_base
    # (Anthropic uses a different tokenizer but cl100k_base is close enough)
    if "claude" in model_lower:
        return tiktoken.get_encoding("cl100k_base")

    # Default fallback
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(messages: list[dict], model: str = "gpt-4") -> int:
    """Count tokens for a list of messages.

    Args:
        messages: List of message dicts with "role" and "content" keys
        model: Model name for tokenizer selection

    Returns:
        Total token count
    """
    encoding = get_encoding_for_model(model)
    token_count = 0

    for message in messages:
        # Count tokens for role
        role = message.get("role", "")
        token_count += len(encoding.encode(role))

        # Count tokens for content
        content = message.get("content", "")
        if content:
            token_count += len(encoding.encode(content))

        # Add overhead for message structure (approximate)
        # Every message follows <|start|>{role}\n{content}<|end|>\n
    # Add overhead for the overall message structure
    if messages:
        token_count += 2  # Priming tokens

    return token_count


def count_tokens_for_message(message: dict, model: str = "gpt-4") -> int:
    """Count tokens for a single message.

    Args:
        message: Message dict with "role" and "content" keys
        model: Model name for tokenizer selection

    Returns:
        Token count for the message
    """
    encoding = get_encoding_for_model(model)
    token_count = 0

    # Count tokens for role
    role = message.get("role", "")
    token_count += len(encoding.encode(role))

    # Count tokens for content
    content = message.get("content", "")
    if content:
        token_count += len(encoding.encode(content))

    return token_count


def truncate_messages(
    messages: list[dict],
    max_tokens: int,
    model: str = "gpt-4",
    reserve_tokens: int = DEFAULT_RESPONSE_RESERVE,
) -> list[dict]:
    """Truncate messages to fit within token limit.

    Preserves the system message (first message if role="system") and
    removes oldest messages first.

    Args:
        messages: List of message dicts
        max_tokens: Maximum tokens allowed
        model: Model name for tokenizer selection
        reserve_tokens: Tokens to reserve for response generation

    Returns:
        Truncated list of messages
    """
    if not messages:
        return []

    effective_limit = max_tokens - reserve_tokens

    # Check if we're already within limits
    current_tokens = count_tokens(messages, model)
    if current_tokens <= effective_limit:
        return messages.copy()

    # Find system message if present
    system_message = None
    start_index = 0
    if messages and messages[0].get("role") == "system":
        system_message = messages[0]
        start_index = 1
        system_tokens = count_tokens_for_message(system_message, model)
        effective_limit -= system_tokens

    # Work backwards from most recent messages
    truncated = []
    total_tokens = 0

    for message in reversed(messages[start_index:]):
        message_tokens = count_tokens_for_message(message, model)

        if total_tokens + message_tokens > effective_limit:
            break

        truncated.insert(0, message)
        total_tokens += message_tokens

    # Add system message back if it exists
    if system_message:
        truncated.insert(0, system_message)

    logger.debug(
        "messages_truncated",
        original_count=len(messages),
        truncated_count=len(truncated),
        original_tokens=current_tokens,
        final_tokens=count_tokens(truncated, model),
    )

    return truncated


def get_model_token_limit(model: str) -> int:
    """Get the token limit for a model.

    Args:
        model: Model name

    Returns:
        Token limit for the model, or default if unknown
    """
    model_lower = model.lower()

    for model_prefix, limit in MODEL_TOKEN_LIMITS.items():
        if model_prefix in model_lower:
            return limit

    # Default fallback
    return 8192


def calculate_available_tokens(
    messages: list[dict],
    model: str = "gpt-4",
    reserve_tokens: int = DEFAULT_RESPONSE_RESERVE,
) -> int:
    """Calculate available tokens for response generation.

    Args:
        messages: Current message list
        model: Model name
        reserve_tokens: Minimum tokens to reserve

    Returns:
        Available tokens for response
    """
    model_limit = get_model_token_limit(model)
    used_tokens = count_tokens(messages, model)
    available = model_limit - used_tokens - reserve_tokens

    return max(0, available)
