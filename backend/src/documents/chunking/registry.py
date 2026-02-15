"""Registry for chunking strategies with auto-selection based on file type."""

from __future__ import annotations

from src.documents.chunking.code_chunker import CodeDocumentChunker
from src.documents.chunking.tabular_chunker import TabularDocumentChunker
from src.core.logging import get_logger

logger = get_logger(__name__)


class ChunkingStrategyRegistry:
    """Registry for domain-specific chunking strategies.

    This registry maps file extensions and content hints to appropriate
    chunking implementations.
    """

    # File extension to strategy mapping
    _EXTENSION_MAP: dict[str, str] = {
        # Code files
        "py": "code",
        "pyi": "code",
        "js": "code",
        "jsx": "code",
        "ts": "code",
        "tsx": "code",
        "java": "code",
        "go": "code",
        "rs": "code",
        "cpp": "code",
        "c": "code",
        "h": "code",
        "cs": "code",
        "php": "code",
        "rb": "code",
        "swift": "code",
        "kt": "code",
        "scala": "code",
        "sh": "code",
        "bash": "code",
        "zsh": "code",
        "sql": "code",
        # Tabular files
        "csv": "tabular",
        "tsv": "tabular",
        "xlsx": "tabular",
        "xls": "tabular",
        # Default
        "txt": "default",
        "md": "default",
        "pdf": "default",
        "docx": "default",
        "doc": "default",
        "rtf": "default",
        "html": "default",
        "json": "default",
        "xml": "default",
        "yaml": "default",
        "yml": "default",
    }

    def __init__(self, max_tokens: int = 500, overlap_tokens: int = 50) -> None:
        """Initialize the registry.

        Args:
            max_tokens: Maximum tokens per chunk (passed to chunkers).
            overlap_tokens: Token overlap between chunks.

        """
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def get_strategy(self, source: str, content_hint: str | None = None) -> str:
        """Get the appropriate strategy for a file.

        Args:
            source: File path or name (used for extension detection).
            content_hint: Optional content type hint (e.g., "table").

        Returns:
            Strategy name: "code", "tabular", or "default".

        """
        # First check explicit content hint
        if content_hint:
            return content_hint

        # Detect from file extension
        ext = self._get_extension(source)
        strategy = self._EXTENSION_MAP.get(ext, "default")

        logger.debug(
            "chunking_strategy_selected",
            source=source,
            extension=ext,
            strategy=strategy,
        )

        return strategy

    def _get_extension(self, source: str) -> str:
        """Extract file extension from source."""
        # Handle cases like "path/to/file.py" or just "file.py"
        if "." in source:
            return source.rsplit(".", 1)[-1].lower()
        return ""

    def create_chunker(self, strategy: str):
        """Create a chunker instance for the given strategy.

        Args:
            strategy: Strategy name ("code", "tabular", "default").

        Returns:
            Chunker instance.

        Raises:
            ValueError: If strategy is unknown.

        """
        if strategy == "code":
            from src.documents.chunker import StructureAwareChunker

            # For code, we can use the existing chunker with code awareness
            # Or use CodeDocumentChunker if implemented
            return CodeDocumentChunker(
                max_tokens=self.max_tokens,
                overlap_tokens=self.overlap_tokens,
            )
        elif strategy == "tabular":
            return TabularDocumentChunker(
                max_tokens=self.max_tokens,
                overlap_tokens=self.overlap_tokens,
            )
        elif strategy == "default":
            from src.documents.chunker import StructureAwareChunker

            return StructureAwareChunker(
                max_tokens=self.max_tokens,
                overlap_tokens=self.overlap_tokens,
            )
        else:
            raise ValueError(f"Unknown chunking strategy: {strategy}")
