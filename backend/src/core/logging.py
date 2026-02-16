"""Structured logging configuration using structlog."""

import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, override

import structlog

# Log file paths
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

APP_LOG_FILE = LOG_DIR / "app.log"
ERROR_LOG_FILE = LOG_DIR / "error.log"
REQUEST_LOG_FILE = LOG_DIR / "request.log"

# ANSI escape code pattern for stripping colors
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

# PII patterns for detection and masking
PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    "ssn": r"\b\d{3}-?\d{2}-?\d{4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "api_key": r"\b(sk-|AKIA|ghp_)[A-Za-z0-9_-]{20,}\b",
    "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
}

# Additional pattern for URLs with credentials (checked separately)
URL_WITH_CREDENTIALS_PATTERN = re.compile(r"https?://[^\s]+:[^\s]+@[^\s]+", re.IGNORECASE)

# Global PII masking configuration
_PII_MASKING_ENABLED = True
_PII_FULL_MASK = False
_PII_MASK_IN_DEBUG = False
_PII_LOGGER: logging.Logger | None = None


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return ANSI_ESCAPE.sub("", text)


def mask_pii_in_message(message: str, full_mask: bool = False) -> tuple[str, list[dict[str, Any]]]:
    """Mask PII in log messages.

    Args:
        message: Original message
        full_mask: If True, completely replace; if False, show partial

    Returns:
        (masked_message, detected_items)
    """
    detected = []
    masked = message

    for pii_type, pattern in PII_PATTERNS.items():
        for match in re.finditer(pattern, message, re.IGNORECASE):
            original = match.group()
            detected.append(
                {
                    "type": pii_type,
                    "position": match.span(),
                    "original": original[:20] + "..." if len(original) > 20 else original,
                }
            )

            if full_mask or pii_type in ("api_key", "ssn"):
                replacement = "***"
            elif pii_type == "email":
                parts = original.split("@")
                replacement = f"{'*' * 3}@{parts[1]}"
            elif pii_type == "ip_address":
                replacement = "***.***.***.***"
            else:
                # Show last 4 chars for phone and credit_card
                replacement = f"***{original[-4:]}"

            masked = masked.replace(original, replacement, 1)

    # Check for URLs with credentials
    for match in URL_WITH_CREDENTIALS_PATTERN.finditer(message):
        original = match.group()
        detected.append(
            {
                "type": "url_with_credentials",
                "position": match.span(),
                "original": original[:30] + "..." if len(original) > 30 else original,
            }
        )
        # Mask the credentials part
        masked = masked.replace(
            original, URL_WITH_CREDENTIALS_PATTERN.sub("https://***:***@***", original), 1
        )

    return masked, detected


def configure_pii_masking(
    enabled: bool = True,
    full_mask: bool = False,
    mask_in_debug: bool = False,
    log_detections: bool = True,
) -> None:
    """Configure PII masking behavior.

    Args:
        enabled: Enable/disable PII masking globally
        full_mask: If True, completely replace PII; if False, show partial
        mask_in_debug: If True, mask even in DEBUG mode; if False, preserve in debug
        log_detections: If True, log PII detection events separately
    """
    global _PII_MASKING_ENABLED, _PII_FULL_MASK, _PII_MASK_IN_DEBUG, _PII_LOGGER
    _PII_MASKING_ENABLED = enabled
    _PII_FULL_MASK = full_mask
    _PII_MASK_IN_DEBUG = mask_in_debug
    if log_detections:
        _PII_LOGGER = logging.getLogger("pii_detection")


def should_mask_pii(log_level: str) -> bool:
    """Determine if PII should be masked based on configuration and log level.

    Args:
        log_level: Current log level

    Returns:
        True if PII should be masked
    """
    return _PII_MASKING_ENABLED and not (log_level.upper() == "DEBUG" and not _PII_MASK_IN_DEBUG)


class CleanFileHandler(logging.Handler):
    """File handler that writes clean, readable logs without ANSI codes."""

    def __init__(self, filepath: Path, max_size_mb: int = 10, max_days: int = 30):
        super().__init__()
        self.filepath = filepath
        self.max_size = max_size_mb * 1024 * 1024
        self.max_days = max_days

    @override
    def emit(self, record: Any) -> None:
        try:
            msg = self.format(record)
            # Strip ANSI codes for clean file output
            clean_msg = strip_ansi(msg)

            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(clean_msg + "\n")

            # Rotate if too large
            if self.filepath.stat().st_size > self.max_size:
                self._rotate()

        except Exception:
            self.handleError(record)

    def _rotate(self) -> None:
        """Rotate log file with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated = self.filepath.with_suffix(f".{timestamp}.log")
        if self.filepath.exists():
            self.filepath.rename(rotated)

        # Cleanup old logs
        self._cleanup_old_logs()

    def _cleanup_old_logs(self) -> None:
        """Delete log files older than max_days."""
        cutoff = datetime.now() - timedelta(days=self.max_days)

        for log_file in self.filepath.parent.glob(f"{self.filepath.stem}.*.log"):
            try:
                # Parse timestamp from filename
                parts = log_file.stem.split(".")
                if len(parts) >= 2:
                    timestamp_str = parts[-1]
                    file_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    if file_time < cutoff:
                        log_file.unlink()
            except (ValueError, OSError):
                pass


def setup_logging(
    log_level: str = "INFO",
    json_format: bool = False,
    log_to_file: bool = True,
    pii_masking_enabled: bool = True,
    pii_full_mask: bool = False,
    pii_mask_in_debug: bool = False,
    pii_log_detections: bool = True,
) -> None:
    """Configure structured logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        json_format: If True, output JSON format; otherwise, console-friendly format
        log_to_file: If True, also write logs to files
        pii_masking_enabled: Enable PII masking in logs
        pii_full_mask: If True, completely replace PII; if False, show partial
        pii_mask_in_debug: If True, mask even in DEBUG mode; if False, preserve in debug
        pii_log_detections: If True, log PII detection events separately
    """
    # Configure PII masking
    configure_pii_masking(
        enabled=pii_masking_enabled,
        full_mask=pii_full_mask,
        mask_in_debug=pii_mask_in_debug,
        log_detections=pii_log_detections,
    )
    # Set standard library logging level
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Console handler (with colors)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)

    # File handlers (without colors)
    if log_to_file:
        # App log (all levels) - clean format
        app_handler = CleanFileHandler(APP_LOG_FILE, max_size_mb=10, max_days=30)
        app_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        app_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(app_handler)

        # Error log (errors only)
        error_handler = CleanFileHandler(ERROR_LOG_FILE, max_size_mb=5, max_days=60)
        error_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s\n%(exc_info)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        error_handler.setLevel(logging.ERROR)
        root_logger.addHandler(error_handler)

        # Request log (for API calls)
        request_handler = CleanFileHandler(REQUEST_LOG_FILE, max_size_mb=20, max_days=7)
        request_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        # Create a separate logger for requests
        request_logger = logging.getLogger("request")
        request_logger.addHandler(request_handler)
        request_logger.setLevel(logging.INFO)
        request_logger.propagate = False  # Don't duplicate to root logger

    # Configure structlog processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        processors_list = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors_list = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors_list,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Get a configured logger instance."""
    return structlog.get_logger(name)


def log_request(
    method: str,
    path: str,
    session_id: str | None = None,
    user_message: str | None = None,
    agent: str | None = None,
    response: str | None = None,
    duration_ms: float | None = None,
    status: str = "success",
    error: str | None = None,
    mask_pii: bool = True,
) -> None:
    """Log API request/response in a readable format.

    Args:
        method: HTTP method
        path: Request path
        session_id: Session identifier
        user_message: User's input message
        agent: Agent that handled the request
        response: AI response (truncated if too long)
        duration_ms: Request duration in milliseconds
        status: "success" or "error"
        error: Error message if failed
        mask_pii: If True, apply PII masking to user_message and response
    """
    logger = logging.getLogger("request")
    pii_logger = _PII_LOGGER

    # Truncate long messages
    max_len = 500
    user_msg_processed = None
    if user_message:
        user_msg_processed = (
            user_message[:max_len] + "..." if len(user_message) > max_len else user_message
        )

    response_processed = None
    if response:
        response_processed = response[:max_len] + "..." if len(response) > max_len else response

    # Apply PII masking if enabled
    if mask_pii and should_mask_pii("INFO"):
        if user_msg_processed:
            user_msg_processed, user_pii = mask_pii_in_message(user_msg_processed, _PII_FULL_MASK)
            if user_pii and pii_logger:
                pii_logger.info(
                    f"PII detected in user_message: {len(user_pii)} items",
                    extra={"pii_types": [p["type"] for p in user_pii]},
                )

        if response_processed:
            response_processed, response_pii = mask_pii_in_message(
                response_processed, _PII_FULL_MASK
            )
            if response_pii and pii_logger:
                pii_logger.info(
                    f"PII detected in response: {len(response_pii)} items",
                    extra={"pii_types": [p["type"] for p in response_pii]},
                )

        if error:
            error, error_pii = mask_pii_in_message(error, _PII_FULL_MASK)
            if error_pii and pii_logger:
                pii_logger.warning(
                    f"PII detected in error: {len(error_pii)} items",
                    extra={"pii_types": [p["type"] for p in error_pii]},
                )

    # Build log message
    parts = [f"[{method}] {path}"]

    if session_id:
        parts.append(f"session={session_id[:8]}...")

    if user_msg_processed:
        parts.append(f"| INPUT: {user_msg_processed}")

    if agent:
        parts.append(f"| AGENT: {agent}")

    if response_processed:
        parts.append(f"| OUTPUT: {response_processed}")

    if duration_ms:
        parts.append(f"| {duration_ms:.0f}ms")

    parts.append(f"| {status.upper()}")

    if error:
        parts.append(f"| ERROR: {error}")

    logger.info(" ".join(parts))


def get_recent_logs(lines: int = 100, log_type: str = "app") -> list[str]:
    """Get recent log entries.

    Args:
        lines: Number of lines to return
        log_type: "app", "error", or "request"

    Returns:
        List of log lines (most recent last)
    """
    log_files = {
        "app": APP_LOG_FILE,
        "error": ERROR_LOG_FILE,
        "request": REQUEST_LOG_FILE,
    }

    log_file = log_files.get(log_type, APP_LOG_FILE)
    if not log_file.exists():
        return []

    with open(log_file, encoding="utf-8") as f:
        all_lines = f.readlines()
        return [line.strip() for line in all_lines[-lines:]]


def cleanup_old_logs(max_days: int = 30) -> list[str]:
    """Manually cleanup old log files.

    Args:
        max_days: Delete logs older than this many days

    Returns:
        List of deleted file names
    """
    cutoff = datetime.now() - timedelta(days=max_days)
    deleted = []

    for log_file in LOG_DIR.glob("*.log.*"):
        try:
            parts = log_file.stem.split(".")
            if len(parts) >= 2:
                timestamp_str = parts[-1]
                file_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                if file_time < cutoff:
                    log_file.unlink()
                    deleted.append(log_file.name)
        except (ValueError, OSError):
            pass

    return deleted
