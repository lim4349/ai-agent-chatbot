"""Structure-based document chunker."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .parser import DocumentSection


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


@dataclass
class Chunk:
    """A chunk of a document."""

    id: str
    content: str
    metadata: ChunkMetadata


class StructureAwareChunker:
    """Chunker that respects document structure."""

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

    def chunk(
        self,
        sections: Sequence[DocumentSection],
        source: str = "",
    ) -> list[Chunk]:
        """Chunk document sections respecting structure.

        Args:
            sections: List of document sections to chunk.
            source: Source identifier for the document.

        Returns:
            List of chunks.

        """
        chunks: list[Chunk] = []

        for section in sections:
            section_chunks = self._chunk_section(section, source)
            chunks.extend(section_chunks)

        # Update chunk indices and totals
        for i, chunk in enumerate(chunks):
            chunk.metadata.chunk_index = i
            chunk.metadata.total_chunks = len(chunks)

        return chunks

    def _chunk_section(
        self,
        section: DocumentSection,
        source: str,
    ) -> list[Chunk]:
        """Chunk a single section."""
        # Code blocks and small sections are kept as-is
        if section.section_type == "code":
            return [self._create_chunk(section.content, section, source)]

        if section.section_type == "table" and self._estimate_tokens(section.content) <= self.max_tokens:
            # Try to keep tables together if they fit
            return [self._create_chunk(section.content, section, source)]

        # Split content into chunks
        return self._split_content(section.content, section, source)

    def _split_content(
        self,
        content: str,
        section: DocumentSection,
        source: str,
    ) -> list[Chunk]:
        """Split content into chunks at sentence boundaries."""
        if not content.strip():
            return []

        # If content fits in one chunk, return it
        if self._estimate_tokens(content) <= self.max_tokens:
            return [self._create_chunk(content, section, source)]

        # Split into sentences
        sentences = self._split_into_sentences(content)
        chunks: list[Chunk] = []
        current_chunk: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)

            # If single sentence is too long, split it further
            if sentence_tokens > self.max_tokens:
                # Flush current chunk first
                if current_chunk:
                    chunk_text = " ".join(current_chunk)
                    chunks.append(self._create_chunk(chunk_text, section, source))
                    current_chunk = []
                    current_tokens = 0

                # Split long sentence by words
                sentence_chunks = self._split_long_sentence(sentence, section, source)
                chunks.extend(sentence_chunks)
                continue

            # Check if adding this sentence would exceed limit
            if current_tokens + sentence_tokens > self.max_tokens and current_chunk:
                # Create chunk from accumulated sentences
                chunk_text = " ".join(current_chunk)
                chunks.append(self._create_chunk(chunk_text, section, source))

                # Start new chunk with overlap
                overlap_sentences = self._get_overlap_sentences(current_chunk)
                current_chunk = overlap_sentences + [sentence]
                current_tokens = sum(
                    self._estimate_tokens(s) for s in current_chunk
                )
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append(self._create_chunk(chunk_text, section, source))

        return chunks

    def _split_long_sentence(
        self,
        sentence: str,
        section: DocumentSection,
        source: str,
    ) -> list[Chunk]:
        """Split a long sentence into word-based chunks."""
        words = sentence.split()
        chunks: list[Chunk] = []
        current_words: list[str] = []
        current_tokens = 0

        for word in words:
            word_tokens = self._estimate_tokens(word + " ")

            if current_tokens + word_tokens > self.max_tokens and current_words:
                chunk_text = " ".join(current_words)
                chunks.append(self._create_chunk(chunk_text, section, source))

                # Start new chunk with overlap words
                overlap_word_count = min(
                    len(current_words),
                    self.overlap_tokens // 2,  # Approximate words in overlap
                )
                current_words = current_words[-overlap_word_count:] + [word]
                current_tokens = sum(
                    self._estimate_tokens(w + " ") for w in current_words
                )
            else:
                current_words.append(word)
                current_tokens += word_tokens

        if current_words:
            chunk_text = " ".join(current_words)
            chunks.append(self._create_chunk(chunk_text, section, source))

        return chunks

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

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return count_tokens(text)

    def _create_chunk(
        self,
        content: str,
        section: DocumentSection,
        source: str,
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
        )

        return Chunk(
            id=str(uuid.uuid4()),
            content=content,
            metadata=metadata,
        )
