"""Domain-aware chunker facade that auto-selects appropriate strategy."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.documents.parser import DocumentSection

from src.core.logging import get_logger
from src.core.protocols import DocumentChunker
from src.documents.chunking.base import Chunk
from src.documents.chunking.registry import ChunkingStrategyRegistry

logger = get_logger(__name__)


class DomainAwareChunker(DocumentChunker):
    """Domain-aware chunker that auto-selects strategy based on file type.

    This chunker implements the DocumentChunker Protocol and serves as
    a facade that delegates to the appropriate domain-specific chunker.
    """

    def __init__(
        self,
        max_tokens: int = 500,
        overlap_tokens: int = 50,
        strategy: str = "auto",
    ) -> None:
        """Initialize the domain-aware chunker.

        Args:
            max_tokens: Maximum tokens per chunk.
            overlap_tokens: Token overlap between chunks.
            strategy: Chunking strategy to use. "auto" for auto-detection,
                "code", "tabular", or "default" for explicit selection.

        """
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.strategy = strategy

        # Create registry for strategy selection
        self._registry = ChunkingStrategyRegistry(max_tokens, overlap_tokens)

    @override
    def chunk(
        self,
        sections: Sequence[DocumentSection],
        source: str = "",
    ) -> list[Chunk]:
        """Chunk document sections using domain-specific strategy.

        Args:
            sections: List of document sections to chunk.
            source: Source identifier for the document (used for strategy selection).

        Returns:
            List of chunks.

        """
        # Determine which strategy to use
        strategy = self._get_strategy(source, sections)

        # Get appropriate chunker for this strategy
        chunker = self._registry.create_chunker(strategy)

        # Delegate to the domain-specific chunker
        chunks = chunker.chunk(sections, source)

        logger.info(
            "chunking_completed",
            source=source,
            strategy=strategy,
            chunks_count=len(chunks),
            total_tokens=sum(c.metadata.token_count for c in chunks),
        )

        return chunks

    def _get_strategy(self, source: str, sections: Sequence[DocumentSection]) -> str:
        """Determine the appropriate chunking strategy.

        Args:
            source: File source (used for extension detection).
            sections: Document sections (used for content hint detection).

        Returns:
            Strategy name.

        """
        # If explicit strategy is set, use it
        if self.strategy != "auto":
            return self.strategy

        # Auto-detect from file extension
        strategy = self._registry.get_strategy(source)

        # Additional content-based detection for ambiguous cases
        if strategy == "default" and sections:
            # Check if content is mostly tabular
            table_ratio = sum(
                1 for s in sections if s.section_type == "table"
            ) / len(sections)

            if table_ratio > 0.5:
                logger.debug(
                    "content_hint_tabular",
                    source=source,
                    table_ratio=table_ratio,
                )
                return "tabular"

        return strategy
