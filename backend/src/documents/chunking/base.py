"""Base chunker with shared utilities."""

import re
import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.documents.parser import DocumentSection


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens in text using tiktoken.

    Falls back to approximate count if tiktoken is not available.
    """
    try:
        import tiktoken

        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except ImportError:
        # Approximate: ~4 characters per token on average
        return len(text) // 4


@dataclass
class ChunkMetadata:
    """Metadata for a document chunk."""

    source: str
    page: int | None = None
    heading: str | None = None
    section_type: str = "paragraph"
    chunk_index: int = 0
    total_chunks: int = 0
    char_count: int = 0
    token_count: int = 0
    language: str | None = None  # For code chunks
    function_name: str | None = None  # For code chunks


@dataclass
class Chunk:
    """A chunk of a document."""

    id: str
    content: str
    metadata: ChunkMetadata


class BaseChunker(ABC):
    """Abstract base class for chunking strategies.

    Subclasses must implement the chunk() method with domain-specific logic.
    """

    def __init__(self, max_tokens: int = 500, overlap_tokens: int = 50) -> None:
        """Initialize the chunker.

        Args:
            max_tokens: Maximum tokens per chunk.
            overlap_tokens: Number of tokens to overlap between chunks.

        """
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        # Approximate chars per token for rough estimation
        self.chars_per_token = 4
        self.max_chars = max_tokens * self.chars_per_token
        self.overlap_chars = overlap_tokens * self.chars_per_token

    @abstractmethod
    def chunk(
        self,
        sections: Sequence["DocumentSection"],
        source: str = "",
    ) -> list[Chunk]:
        """Chunk document sections using domain-specific strategy.

        Args:
            sections: List of document sections to chunk.
            source: Source identifier for the document.

        Returns:
            List of chunks.

        """
        ...

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return count_tokens(text)

    def _create_chunk(
        self,
        content: str,
        section: "DocumentSection",
        source: str,
        **extra_metadata,
    ) -> Chunk:
        """Create a chunk with metadata."""
        token_count = self._estimate_tokens(content)

        metadata = ChunkMetadata(
            source=source,
            page=section.page,
            heading=section.heading,
            section_type=section.section_type,
            char_count=len(content),
            token_count=token_count,
            **extra_metadata,
        )

        return Chunk(
            id=str(uuid.uuid4()),
            content=content,
            metadata=metadata,
        )

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting on period, question mark, exclamation
        # followed by space or end of string
        pattern = r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\s*$'
        sentences = re.split(pattern, text.strip())
        return [s.strip() for s in sentences if s.strip()]

    def _get_overlap_sentences(self, sentences: list[str]) -> list[str]:
        """Get sentences for overlap based on token count."""
        overlap: list[str] = []
        overlap_tokens = 0

        for sentence in reversed(sentences):
            sentence_tokens = self._estimate_tokens(sentence)
            if overlap_tokens + sentence_tokens <= self.overlap_tokens:
                overlap.insert(0, sentence)
                overlap_tokens += sentence_tokens
            else:
                break

        return overlap

    def _update_chunk_indices(self, chunks: list[Chunk]) -> None:
        """Update chunk_index and total_chunks for all chunks."""
        for i, chunk in enumerate(chunks):
            chunk.metadata.chunk_index = i
            chunk.metadata.total_chunks = len(chunks)
