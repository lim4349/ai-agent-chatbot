"""Tabular data chunker that preserves table structure."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.documents.parser import DocumentSection

from src.documents.chunking.base import BaseChunker, Chunk


class TabularDocumentChunker(BaseChunker):
    """Chunker for tabular data (CSV, TSV) that preserves table structure.

    This chunker keeps headers together with data rows and can chunk
    large tables by row groups while maintaining column context.
    """

    @override
    def chunk(
        self,
        sections: Sequence[DocumentSection],
        source: str = "",
    ) -> list[Chunk]:
        """Chunk tabular sections preserving headers."""
        chunks: list[Chunk] = []

        for section in sections:
            if section.section_type == "table":
                section_chunks = self._chunk_table_section(section, source)
                chunks.extend(section_chunks)
            else:
                # For non-table sections, use simple chunking
                section_chunks = self._chunk_simple(section, source)
                chunks.extend(section_chunks)

        self._update_chunk_indices(chunks)
        return chunks

    def _chunk_table_section(
        self,
        section: DocumentSection,
        source: str,
    ) -> list[Chunk]:
        """Chunk a table section preserving headers."""
        content = section.content

        # If content is small enough, keep as one chunk
        if self._estimate_tokens(content) <= self.max_tokens:
            return [self._create_chunk(content, section, source)]

        # Parse table into header and rows
        lines = content.split("\n")
        if not lines:
            return []

        # First line is typically the header
        header = lines[0]
        rows = lines[1:]

        # Calculate how many rows fit per chunk
        header_tokens = self._estimate_tokens(header)
        available_tokens = self.max_tokens - header_tokens - self.overlap_tokens

        if available_tokens <= 0:
            # Header alone is too large, chunk everything
            return self._chunk_simple(section, source)

        # Estimate tokens per row (average)
        avg_row_tokens = (
            sum(self._estimate_tokens(row) for row in rows) // len(rows) if rows else 100
        )

        rows_per_chunk = max(1, available_tokens // avg_row_tokens)

        # Create chunks with header + row groups
        chunks: list[Chunk] = []
        row_groups = self._group_rows(rows, rows_per_chunk)

        for row_group in row_groups:
            chunk_content = header + "\n" + "\n".join(row_group)
            chunks.append(self._create_chunk(chunk_content, section, source))

        return chunks

    def _group_rows(self, rows: list[str], rows_per_chunk: int) -> list[list[str]]:
        """Group rows into chunks with overlap."""
        if not rows:
            return []

        groups: list[list[str]] = []
        current_group: list[str] = []

        for row in rows:
            current_group.append(row)

            if len(current_group) >= rows_per_chunk:
                groups.append(current_group)

                # Start next group with overlap rows
                overlap = min(rows_per_chunk // 2, len(current_group))
                current_group = current_group[-overlap:]

        # Don't forget the last group
        if current_group:
            groups.append(current_group)

        return groups

    def _chunk_simple(
        self,
        section: DocumentSection,
        source: str,
    ) -> list[Chunk]:
        """Fallback simple chunking for non-table content."""
        content = section.content

        if self._estimate_tokens(content) <= self.max_tokens:
            return [self._create_chunk(content, section, source)]

        # Split by sentences
        sentences = self._split_into_sentences(content)
        chunks: list[Chunk] = []
        current_sentences: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)

            # Check if adding this sentence would exceed limit
            if current_tokens + sentence_tokens > self.max_tokens and current_sentences:
                # Create chunk from accumulated sentences
                chunk_text = " ".join(current_sentences)
                chunks.append(self._create_chunk(chunk_text, section, source))

                # Start new chunk with overlap
                overlap_sentences = self._get_overlap_sentences(current_sentences)
                current_sentences = overlap_sentences + [sentence]
                current_tokens = sum(self._estimate_tokens(s) for s in current_sentences)
            else:
                current_sentences.append(sentence)
                current_tokens += sentence_tokens

        # Don't forget the last chunk
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            chunks.append(self._create_chunk(chunk_text, section, source))

        return chunks
