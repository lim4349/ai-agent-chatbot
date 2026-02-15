"""Input validation utilities for AI Agent Chatbot.

This module provides comprehensive input validation functions to ensure
security and data integrity across the application.

Functions return tuples of (is_valid, error_message) or (is_valid, error_message, metadata)
for consistent error handling throughout the application.
"""

import json
import re
from functools import lru_cache
from typing import Any

# =============================================================================
# Constants
# =============================================================================

# Message validation
MAX_MESSAGE_LENGTH: int = 2000
MIN_MESSAGE_LENGTH: int = 1

# File upload validation
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10MB
MIN_FILE_SIZE_BYTES: int = 1  # At least 1 byte

# Allowed file extensions and their magic byte patterns
ALLOWED_FILE_TYPES: dict[str, dict[str, Any]] = {
    "pdf": {
        "magic_bytes": [b"%PDF-"],
        "mime_types": ["application/pdf"],
        "description": "Portable Document Format",
    },
    "docx": {
        "magic_bytes": [b"PK\x03\x04"],  # ZIP container
        "mime_types": [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ],
        "description": "Microsoft Word Document",
    },
    "txt": {
        "magic_bytes": [],  # Text files have no magic bytes
        "mime_types": ["text/plain"],
        "description": "Plain Text File",
    },
    "md": {
        "magic_bytes": [],  # Markdown is text
        "mime_types": ["text/markdown", "text/plain"],
        "description": "Markdown File",
    },
    "csv": {
        "magic_bytes": [],  # CSV is text
        "mime_types": ["text/csv", "application/csv"],
        "description": "Comma Separated Values",
    },
    "json": {
        "magic_bytes": [b"{", b"["],  # Common JSON start bytes
        "mime_types": ["application/json"],
        "description": "JSON Data",
    },
}

# Session ID validation
SESSION_ID_MIN_LENGTH: int = 16
SESSION_ID_MAX_LENGTH: int = 256
SESSION_ID_PATTERN: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_-]+$")

# JSON validation
MAX_JSON_SIZE_KB: int = 100
MAX_JSON_NESTING_DEPTH: int = 20

# Metadata validation
MAX_METADATA_KEY_LENGTH: int = 100
MAX_METADATA_STRING_LENGTH: int = 1000
MAX_METADATA_DEPTH: int = 10

# Injection patterns to detect
INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\$\{.*?\}"),  # Template injection
    re.compile(r"<script", re.IGNORECASE),  # Script tags (opening)
    re.compile(r"__import__\s*\("),  # Python import injection
    re.compile(r"eval\s*\("),  # Eval injection
    re.compile(r"exec\s*\("),  # Exec injection
    re.compile(r"base64\.decode"),  # Base64 decode attempts
    re.compile(r"pickle\.loads"),  # Pickle injection
    re.compile(r"subprocess\.|os\.system|os\.popen"),  # Command injection
    re.compile(r"<\?php"),  # PHP injection
    re.compile(r"<%.*?%>"),  # JSP/ASP injection
]

# ReDoS patterns - patterns that could cause catastrophic backtracking
# Note: These are simplified patterns to catch common ReDoS attempts
# without being overly aggressive on normal text
REDOS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\(.+\)\*\*"),  # Complex nested quantifiers
    re.compile(r"\[.+\]\{.*\}\+"),  # Ambiguous quantifier combinations
    re.compile(r".+\*\{.*\}"),  # Star with brace quantifiers
]

# PII detection patterns
PII_PATTERNS: dict[str, dict[str, Any]] = {
    "email": {
        "pattern": re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        ),
        "description": "Email address",
        "severity": "medium",
    },
    "phone": {
        "pattern": re.compile(
            r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
        ),
        "description": "Phone number (US format)",
        "severity": "medium",
    },
    "ssn": {
        "pattern": re.compile(r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b"),
        "description": "Social Security Number",
        "severity": "high",
    },
    "credit_card": {
        "pattern": re.compile(
            r"\b(?:\d{4}[-.\s]?){3}\d{4}\b",
        ),
        "description": "Credit card number",
        "severity": "high",
    },
    "api_key": {
        "pattern": re.compile(
            r"\b[A-Za-z0-9]{32,}\b",  # Generic long alphanumeric strings
        ),
        "description": "Potential API key or token",
        "severity": "high",
    },
    "ip_address": {
        "pattern": re.compile(
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
            r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        ),
        "description": "IP address",
        "severity": "low",
    },
}

# Whitespace validation
MAX_CONSECUTIVE_SPACES: int = 10
MAX_CONSECUTIVE_NEWLINES: int = 5


# =============================================================================
# Exceptions
# =============================================================================


class ValidationError(Exception):
    """Custom validation error with detailed context.

    Attributes:
        message: Human-readable error description
        field: Name of the field that failed validation
        value: The value that failed validation
        code: Error code for programmatic handling
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        code: str = "VALIDATION_ERROR",
    ) -> None:
        """Initialize validation error.

        Args:
            message: Human-readable error description
            field: Name of the field that failed validation
            value: The value that failed validation
            code: Error code for programmatic handling
        """
        self.message = message
        self.field = field
        self.value = value
        self.code = code
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for API responses.

        Returns:
            Dictionary containing error details
        """
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.field:
            result["field"] = self.field
        if self.value is not None:
            result["value"] = str(self.value)[:100]  # Limit value length
        return result


# =============================================================================
# Message Content Validation
# =============================================================================


def validate_message_content(content: str) -> tuple[bool, str | None]:
    """Validate user message content for security and formatting.

    Performs comprehensive validation including:
    - Length limits (1-2000 characters)
    - Null byte detection
    - Injection pattern detection
    - ReDoS prevention
    - Excessive whitespace check

    Args:
        content: The message content to validate

    Returns:
        Tuple of (is_valid, error_message). Returns (True, None) if valid.

    Examples:
        >>> validate_message_content("Hello, world!")
        (True, None)

        >>> validate_message_content("${malicious code}")
        (False, "Message contains potential injection patterns")
    """
    if not isinstance(content, str):
        return False, "Message content must be a string"

    # Null byte check
    if "\x00" in content:
        return False, "Message contains null bytes"

    # Length validation
    if len(content) < MIN_MESSAGE_LENGTH:
        return False, f"Message must be at least {MIN_MESSAGE_LENGTH} character(s)"
    if len(content) > MAX_MESSAGE_LENGTH:
        return False, f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters"

    # Injection pattern detection
    for pattern in INJECTION_PATTERNS:
        if pattern.search(content):
            return False, "Message contains potential injection patterns"

    # ReDoS pattern detection
    for pattern in REDOS_PATTERNS:
        if pattern.search(content):
            return False, "Message contains patterns that could cause performance issues"

    # Excessive whitespace check
    if " " * (MAX_CONSECUTIVE_SPACES + 1) in content:
        return False, f"Message contains excessive consecutive spaces (max {MAX_CONSECUTIVE_SPACES})"
    if "\n" * (MAX_CONSECUTIVE_NEWLINES + 1) in content:
        return False, f"Message contains excessive consecutive newlines (max {MAX_CONSECUTIVE_NEWLINES})"

    return True, None


# =============================================================================
# Session ID Validation
# =============================================================================


def validate_session_id(session_id: str) -> tuple[bool, str | None]:
    """Validate session ID format and content.

    Validates that the session ID:
    - Is alphanumeric with hyphens and underscores only
    - Falls within length limits (16-256 characters)
    - Does not contain path traversal sequences
    - Does not contain null bytes

    Args:
        session_id: The session ID to validate

    Returns:
        Tuple of (is_valid, error_message). Returns (True, None) if valid.

    Examples:
        >>> validate_session_id("session_abc-123")
        (True, None)

        >>> validate_session_id("../etc/passwd")
        (False, "Session ID contains invalid characters")
    """
    if not isinstance(session_id, str):
        return False, "Session ID must be a string"

    # Null byte check
    if "\x00" in session_id:
        return False, "Session ID contains null bytes"

    # Length validation
    if len(session_id) < SESSION_ID_MIN_LENGTH:
        return False, f"Session ID must be at least {SESSION_ID_MIN_LENGTH} characters"
    if len(session_id) > SESSION_ID_MAX_LENGTH:
        return False, f"Session ID exceeds maximum length of {SESSION_ID_MAX_LENGTH} characters"

    # Path traversal detection
    if ".." in session_id:
        return False, "Session ID contains path traversal sequences"

    # Format validation
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        return False, "Session ID contains invalid characters (only alphanumeric, hyphen, underscore allowed)"

    return True, None


# =============================================================================
# File Upload Validation
# =============================================================================


@lru_cache(maxsize=128)
def _get_magic_detector():
    """Get magic number detector with caching.

    Returns:
        Magic detector function or None if not available

    Note:
        Uses lru_cache to avoid repeated import attempts and initialization.
        Returns None if python-magic is not available.
    """
    try:
        import magic

        return magic.Magic(mime=True)
    except ImportError:
        return None


def _detect_file_type_by_bytes(content: bytes) -> str | None:
    """Detect file type by examining magic bytes.

    Args:
        content: File content as bytes

    Returns:
        Detected file extension (without dot) or None if unknown
    """
    if not content:
        return None

    # Check magic bytes for each allowed type
    for ext, type_info in ALLOWED_FILE_TYPES.items():
        if not type_info["magic_bytes"]:
            continue  # Text-based types have no magic bytes

        for magic_bytes in type_info["magic_bytes"]:
            if content.startswith(magic_bytes):
                # Additional check for docx (which is a ZIP)
                if ext == "docx":
                    # Check for [Content_Types].xml in ZIP
                    if b"[Content_Types].xml" in content[:1000]:
                        return ext
                else:
                    return ext

    return None


def _validate_file_extension(filename: str) -> tuple[bool, str | None, str]:
    """Validate and extract file extension.

    Args:
        filename: Name of the file

    Returns:
        Tuple of (is_valid, error_message, extension)
    """
    if not filename:
        return False, "Filename is required", ""

    # Path traversal check
    if ".." in filename or "/" in filename or "\\" in filename:
        return False, "Filename contains path traversal sequences", ""

    # Null byte check
    if "\x00" in filename:
        return False, "Filename contains null bytes", ""

    # Extract extension
    parts = filename.rsplit(".", 1)
    if len(parts) != 2:
        return False, "File must have an extension", ""

    ext = parts[1].lower()

    if ext not in ALLOWED_FILE_TYPES:
        allowed = ", ".join(sorted(ALLOWED_FILE_TYPES.keys()))
        return False, f"File type '.{ext}' not allowed. Allowed types: {allowed}", ext

    return True, None, ext


def _validate_file_content_size(content: bytes) -> tuple[bool, str | None]:
    """Validate file content size.

    Args:
        content: File content as bytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not content:
        return False, "File content is empty"

    size = len(content)
    if size < MIN_FILE_SIZE_BYTES:
        return False, f"File is too small (minimum {MIN_FILE_SIZE_BYTES} byte)"

    if size > MAX_FILE_SIZE_BYTES:
        size_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        return False, f"File size exceeds maximum of {size_mb:.0f}MB"

    return True, None


def _is_text_file(content: bytes, ext: str) -> bool:
    """Check if file appears to be text-based.

    Args:
        content: File content as bytes
        ext: File extension

    Returns:
        True if file appears to be text
    """
    # For known text extensions
    if ext in ["txt", "md", "csv", "json"]:
        # Check for non-text characters (excluding common whitespace)
        try:
            content.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    return False


def validate_file_upload(
    filename: str,
    content: bytes,
    declared_mime_type: str | None = None,
) -> tuple[bool, str | None, dict[str, Any]]:
    """Comprehensive file upload validation.

    Validates file uploads with multiple layers of security:
    - Filename validation (no path traversal, valid extension)
    - File size limits (1 byte to 10MB)
    - Extension whitelist enforcement
    - Magic byte verification
    - MIME type consistency check

    Args:
        filename: Name of the uploaded file
        content: File content as bytes
        declared_mime_type: Optional declared MIME type from upload

    Returns:
        Tuple of (is_valid, error_message, metadata).
        Metadata includes detected_type, size_bytes, is_text, etc.

    Examples:
        >>> with open("doc.pdf", "rb") as f:
        ...     content = f.read()
        >>> is_valid, error, meta = validate_file_upload("doc.pdf", content)
        >>> is_valid
        True
    """
    metadata: dict[str, Any] = {
        "filename": filename,
        "size_bytes": len(content) if content else 0,
        "detected_type": None,
        "is_text": False,
        "magic_match": False,
        "mime_consistent": True,
    }

    # Validate filename and extension
    is_valid, error, ext = _validate_file_extension(filename)
    if not is_valid:
        return False, error, metadata

    metadata["detected_type"] = ext

    # Validate content size
    is_valid, error = _validate_file_content_size(content)
    if not is_valid:
        return False, error, metadata

    # Detect file type from magic bytes
    detected_by_magic = _detect_file_type_by_bytes(content)

    # For text files, check if they're actually text
    is_text = _is_text_file(content, ext)
    metadata["is_text"] = is_text

    # Validate magic byte match
    if ext in ["txt", "md", "csv", "json"]:
        # Text files - no magic bytes to check
        if not is_text:
            return (
                False,
                f"File content does not appear to be valid text for '.{ext}' file",
                metadata,
            )
    else:
        # Binary files - must match magic bytes
        if detected_by_magic != ext:
            metadata["magic_match"] = False
            if detected_by_magic:
                return (
                    False,
                    f"File content magic bytes indicate '.{detected_by_magic}', not '.{ext}'",
                    metadata,
                )
            else:
                return (
                    False,
                    f"File content does not match expected magic bytes for '.{ext}'",
                    metadata,
                )

    metadata["magic_match"] = True

    # MIME type validation if provided
    if declared_mime_type:
        expected_mimes = ALLOWED_FILE_TYPES[ext]["mime_types"]
        if declared_mime_type not in expected_mimes:
            metadata["mime_consistent"] = False
            return (
                False,
                f"Declared MIME type '{declared_mime_type}' does not match expected types for '.{ext}': {expected_mimes}",
                metadata,
            )

    return True, None, metadata


# =============================================================================
# Metadata Sanitization
# =============================================================================


def _sanitize_string(value: str, max_length: int) -> str:
    """Sanitize a string value.

    Args:
        value: String to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        value = str(value)

    # Remove null bytes
    value = value.replace("\x00", "")

    # Truncate if too long
    if len(value) > max_length:
        value = value[:max_length]

    return value


def _sanitize_metadata_value(value: Any, depth: int) -> Any:
    """Recursively sanitize a metadata value.

    Args:
        value: Value to sanitize
        depth: Current nesting depth

    Returns:
        Sanitized value

    Raises:
        ValidationError: If nesting depth exceeds maximum
    """
    if depth > MAX_METADATA_DEPTH:
        raise ValidationError(
            f"Metadata nesting depth exceeds maximum of {MAX_METADATA_DEPTH}",
            code="METADATA_DEPTH_EXCEEDED",
        )

    if value is None:
        return None

    if isinstance(value, str):
        return _sanitize_string(value, MAX_METADATA_STRING_LENGTH)

    if isinstance(value, (int, float, bool)):
        return value

    if isinstance(value, list):
        return [_sanitize_metadata_value(item, depth + 1) for item in value]

    if isinstance(value, dict):
        return _sanitize_metadata_dict(value, depth + 1)

    # For other types, convert to string
    return _sanitize_string(str(value), MAX_METADATA_STRING_LENGTH)


def _sanitize_metadata_dict(metadata: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    """Recursively sanitize a metadata dictionary.

    Args:
        metadata: Dictionary to sanitize
        depth: Current nesting depth

    Returns:
        Sanitized dictionary

    Raises:
        ValidationError: If nesting depth exceeds maximum
    """
    sanitized: dict[str, Any] = {}

    for key, value in metadata.items():
        # Sanitize key
        if not isinstance(key, str):
            key = str(key)
        key = _sanitize_string(key, MAX_METADATA_KEY_LENGTH)

        # Validate key name (prevent injection)
        if not key or not key.replace("_", "").replace("-", "").isalnum():
            # Skip keys with invalid names
            continue

        # Sanitize value
        try:
            sanitized[key] = _sanitize_metadata_value(value, depth)
        except ValidationError:
            # Skip values that can't be sanitized
            continue

    return sanitized


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Sanitize metadata dictionary to prevent security issues.

    Sanitization includes:
    - Removing null bytes from all strings
    - Truncating excessive string lengths
    - Validating key names
    - Sanitizing nested structures
    - Limiting nesting depth

    Args:
        metadata: Metadata dictionary to sanitize

    Returns:
        Sanitized metadata dictionary

    Examples:
        >>> sanitize_metadata({"user": "john", "data": "test\\x00"})
        {'user': 'john', 'data': 'test'}

        >>> sanitize_metadata({"nested": {"deep": {"value": "x" * 2000}}})
        {'nested': {'deep': {'value': 'x' * 1000}}}
    """
    if not isinstance(metadata, dict):
        # If not a dict, return empty dict
        return {}

    return _sanitize_metadata_dict(metadata)


# =============================================================================
# PII Detection
# =============================================================================


def detect_pii_content(content: str) -> list[dict[str, Any]]:
    """Detect potentially sensitive PII (Personally Identifiable Information) in content.

    Scans content for various PII patterns including:
    - Email addresses
    - Phone numbers
    - Social Security Numbers
    - Credit card numbers
    - API keys/tokens
    - IP addresses

    Args:
        content: Text content to scan

    Returns:
        List of detected PII items with metadata including:
        - type: Type of PII detected
        - match: The matched text
        - start: Start position in content
        - end: End position in content
        - severity: Severity level (low, medium, high)
        - description: Human-readable description

    Examples:
        >>> detect_pii_content("Contact me at user@example.com")
        [{'type': 'email', 'match': 'user@example.com', 'start': 13, 'end': 29, ...}]
    """
    if not isinstance(content, str):
        return []

    detections: list[dict[str, Any]] = []

    for pii_type, pii_info in PII_PATTERNS.items():
        pattern = pii_info["pattern"]
        description = pii_info["description"]
        severity = pii_info["severity"]

        for match in pattern.finditer(content):
            detection: dict[str, Any] = {
                "type": pii_type,
                "match": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "description": description,
                "severity": severity,
            }
            detections.append(detection)

    # Sort by position
    detections.sort(key=lambda x: x["start"])

    return detections


def has_sensitive_pii(content: str, min_severity: str = "medium") -> bool:
    """Check if content contains sensitive PII above threshold.

    Args:
        content: Text content to check
        min_severity: Minimum severity level ("low", "medium", "high")

    Returns:
        True if sensitive PII is detected

    Examples:
        >>> has_sensitive_pii("My email is user@example.com")
        True

        >>> has_sensitive_pii("Hello world", min_severity="high")
        False
    """
    severity_levels = {"low": 0, "medium": 1, "high": 2}
    min_level = severity_levels.get(min_severity, 1)

    detections = detect_pii_content(content)

    for detection in detections:
        detection_level = severity_levels.get(detection["severity"], 0)
        if detection_level >= min_level:
            return True

    return False


# =============================================================================
# JSON Size Validation
# =============================================================================


def validate_json_size(json_str: str, max_size_kb: int = MAX_JSON_SIZE_KB) -> tuple[bool, str | None]:
    """Validate JSON string size and structure.

    Validates:
    - Size in KB (to prevent DoS)
    - Nesting depth (to prevent stack overflow)
    - Valid JSON syntax

    Args:
        json_str: JSON string to validate
        max_size_kb: Maximum size in kilobytes

    Returns:
        Tuple of (is_valid, error_message). Returns (True, None) if valid.

    Examples:
        >>> validate_json_size('{"key": "value"}')
        (True, None)

        >>> validate_json_size('a' * 200000)
        (False, "JSON size exceeds maximum of 100KB")
    """
    if not isinstance(json_str, str):
        return False, "JSON input must be a string"

    # Size check
    size_bytes = len(json_str.encode("utf-8"))
    size_kb = size_bytes / 1024

    if size_kb > max_size_kb:
        return False, f"JSON size exceeds maximum of {max_size_kb}KB (got {size_kb:.1f}KB)"

    # Try to parse and check nesting
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON syntax: {str(e)}"

    # Check nesting depth
    def get_depth(obj: Any, current_depth: int = 0) -> int:
        """Recursively calculate maximum nesting depth."""
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(get_depth(v, current_depth + 1) for v in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(get_depth(item, current_depth + 1) for item in obj)
        else:
            return current_depth

    depth = get_depth(parsed)
    if depth > MAX_JSON_NESTING_DEPTH:
        return False, f"JSON nesting depth exceeds maximum of {MAX_JSON_NESTING_DEPTH} (got {depth})"

    return True, None


# =============================================================================
# Batch Validation
# =============================================================================


def validate_chat_input(
    message: str,
    session_id: str,
    metadata: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """Validate all chat input fields together.

    Convenience function to validate message, session ID, and metadata
    in a single call.

    Args:
        message: User message content
        session_id: Session identifier
        metadata: Optional metadata dictionary

    Returns:
        Tuple of (is_valid, list_of_errors). If is_valid is True,
        errors list will be empty.

    Examples:
        >>> validate_chat_input("Hello!", "session_123", {"user": "john"})
        (True, [])

        >>> validate_chat_input("", "bad@id", {})
        (False, ['Message must be at least 1 character(s)',
                  'Session ID contains invalid characters...'])
    """
    errors: list[str] = []

    # Validate message
    is_valid, error = validate_message_content(message)
    if not is_valid and error:
        errors.append(f"Message: {error}")

    # Validate session ID
    is_valid, error = validate_session_id(session_id)
    if not is_valid and error:
        errors.append(f"Session ID: {error}")

    # Sanitize metadata if provided
    if metadata:
        try:
            sanitize_metadata(metadata)
        except ValidationError as e:
            errors.append(f"Metadata: {e.message}")

    return len(errors) == 0, errors


# =============================================================================
# Utility Functions
# =============================================================================


def truncate_message(message: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
    """Truncate message to maximum length with ellipsis if needed.

    Args:
        message: Message to truncate
        max_length: Maximum allowed length

    Returns:
        Truncated message with "..." appended if truncated
    """
    if len(message) <= max_length:
        return message
    return message[: max_length - 3] + "..."


def escape_html(text: str) -> str:
    """Escape HTML special characters to prevent XSS.

    Args:
        text: Text to escape

    Returns:
        HTML-escaped text

    Examples:
        >>> escape_html("<script>alert('xss')</script>")
        '&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;'
    """
    if not isinstance(text, str):
        text = str(text)

    escape_map = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
    }

    result = []
    for char in text:
        result.append(escape_map.get(char, char))
    return "".join(result)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing potentially dangerous characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for filesystem use

    Examples:
        >>> sanitize_filename("../../etc/passwd")
        'etcpasswd'

        >>> sanitize_filename("my document.pdf")
        'my_document.pdf'
    """
    if not isinstance(filename, str):
        filename = str(filename)

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Remove path components
    filename = filename.replace("/", "").replace("\\", "")

    # Replace multiple dots with single dot
    while ".." in filename:
        filename = filename.replace("..", ".")

    # Remove leading/trailing dots that might result from path traversal removal
    filename = filename.strip(".")

    # Replace spaces with underscores
    filename = filename.replace(" ", "_")

    # Remove any remaining non-alphanumeric characters except dots, hyphens, underscores
    filename = "".join(c for c in filename if c.isalnum() or c in "._-")

    # Ensure filename isn't empty
    if not filename:
        filename = "unnamed"

    return filename
