"""Hierarchy-aware parent-child document chunker."""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

from src.documents.models import Chunk, ChunkMetadata

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .parser import DocumentSection


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens using tiktoken, falling back to an approximate count."""
    try:
        import tiktoken

        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except ImportError:
        return len(text) // 4


class StructureAwareChunker:
    """Chunker that preserves hierarchy and emits parent-child retrieval records."""

    def __init__(self, max_tokens: int = 500, overlap_tokens: int = 50) -> None:
        """Initialize the chunker.

        Args:
            max_tokens: Maximum tokens for parent context chunks.
            overlap_tokens: Token overlap between adjacent chunks.
        """
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.child_max_tokens = self._child_token_budget(max_tokens)

    def chunk(
        self,
        sections: Sequence[DocumentSection],
        source: str = "",
    ) -> list[Chunk]:
        """Chunk document sections into parent context and child search records."""
        chunks: list[Chunk] = []

        for section in sections:
            if not section.content.strip() or section.section_type == "heading":
                continue

            for parent_text in self._split_parent_content(section):
                parent = self._create_chunk(parent_text, section, source, record_type="parent")
                parent.metadata.parent_id = parent.id
                chunks.append(parent)

                child_texts = self._split_child_content(parent_text, section)
                for child_text in child_texts:
                    child = self._create_chunk(
                        child_text,
                        section,
                        source,
                        record_type="child",
                        parent_id=parent.id,
                    )
                    child.metadata.child_id = child.id
                    chunks.append(child)

        self._update_chunk_indices(chunks)
        return chunks

    def _split_parent_content(self, section: DocumentSection) -> list[str]:
        """Split one section into parent-sized context chunks."""
        content = self._with_heading_context(section.content, section)
        if section.section_type == "table":
            return self._split_table(content, self.max_tokens)
        return self._split_text(content, self.max_tokens)

    def _split_child_content(self, parent_text: str, section: DocumentSection) -> list[str]:
        """Split one parent context into smaller child search chunks."""
        if self._estimate_tokens(parent_text) <= self.child_max_tokens:
            return [parent_text]
        if section.section_type == "table":
            return self._split_table(parent_text, self.child_max_tokens)
        return self._split_text(parent_text, self.child_max_tokens)

    def _split_text(self, text: str, max_tokens: int) -> list[str]:
        """Recursively split text by semantic-ish separators before words."""
        text = text.strip()
        if not text:
            return []
        if self._estimate_tokens(text) <= max_tokens:
            return [text]

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if len(paragraphs) > 1:
            return self._pack_units(paragraphs, "\n\n", max_tokens)

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) > 1:
            return self._pack_units(lines, "\n", max_tokens)

        sentences = self._split_into_sentences(text)
        if len(sentences) > 1:
            return self._pack_units(sentences, " ", max_tokens)

        return self._split_words(text, max_tokens)

    def _split_table(self, table_text: str, max_tokens: int) -> list[str]:
        """Split Markdown tables by row groups while repeating the header."""
        table_text = table_text.strip()
        if not table_text:
            return []
        if self._estimate_tokens(table_text) <= max_tokens:
            return [table_text]

        lines = [line for line in table_text.splitlines() if line.strip()]
        if len(lines) < 3:
            return self._split_text(table_text, max_tokens)

        heading_prefix: list[str] = []
        while lines and not lines[0].lstrip().startswith("|"):
            heading_prefix.append(lines.pop(0))

        if len(lines) < 3:
            return self._split_text(table_text, max_tokens)

        header = lines[:2]
        rows = lines[2:]
        prefix = "\n".join(heading_prefix)
        header_text = "\n".join([prefix, *header]) if prefix else "\n".join(header)
        chunks: list[str] = []
        current_rows: list[str] = []

        for row in rows:
            candidate = "\n".join([header_text, *current_rows, row])
            if self._estimate_tokens(candidate) > max_tokens and current_rows:
                chunks.append("\n".join([header_text, *current_rows]))
                overlap = current_rows[-1:] if self.overlap_tokens > 0 else []
                current_rows = [*overlap, row]
            else:
                current_rows.append(row)

        if current_rows:
            chunks.append("\n".join([header_text, *current_rows]))

        return chunks

    def _pack_units(self, units: list[str], joiner: str, max_tokens: int) -> list[str]:
        """Pack units into token-limited chunks with overlap."""
        chunks: list[str] = []
        current: list[str] = []

        for unit in units:
            if self._estimate_tokens(unit) > max_tokens:
                if current:
                    chunks.append(joiner.join(current))
                    current = []
                chunks.extend(self._split_words(unit, max_tokens))
                continue

            candidate = joiner.join([*current, unit]) if current else unit
            if self._estimate_tokens(candidate) > max_tokens and current:
                chunks.append(joiner.join(current))
                current = [*self._overlap_units(current), unit]
            else:
                current.append(unit)

        if current:
            chunks.append(joiner.join(current))

        return chunks

    def _split_words(self, text: str, max_tokens: int) -> list[str]:
        """Split long text by words as the final fallback."""
        words = text.split()
        chunks: list[str] = []
        current: list[str] = []

        for word in words:
            candidate = " ".join([*current, word]) if current else word
            if self._estimate_tokens(candidate) > max_tokens and current:
                chunks.append(" ".join(current))
                overlap_count = min(len(current), max(1, self.overlap_tokens // 4))
                current = [*current[-overlap_count:], word]
            else:
                current.append(word)

        if current:
            chunks.append(" ".join(current))

        return chunks

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split English and Korean punctuation-delimited sentences."""
        pattern = r"(?<=[.!?。！？]|다\.|요\.)\s+"
        sentences = re.split(pattern, text.strip())
        return [sentence.strip() for sentence in sentences if sentence.strip()]

    def _overlap_units(self, units: list[str]) -> list[str]:
        """Return trailing units whose estimated tokens fit the overlap budget."""
        overlap: list[str] = []
        token_count = 0
        for unit in reversed(units):
            unit_tokens = self._estimate_tokens(unit)
            if token_count + unit_tokens > self.overlap_tokens:
                break
            overlap.insert(0, unit)
            token_count += unit_tokens
        return overlap

    def _with_heading_context(self, content: str, section: DocumentSection) -> str:
        """Prefix content with hierarchy context when available."""
        heading_path = self._heading_path(section)
        if not heading_path:
            return content.strip()
        context = " > ".join(heading_path)
        if content.strip().startswith(context):
            return content.strip()
        return f"Section: {context}\n\n{content.strip()}"

    def _heading_path(self, section: DocumentSection) -> list[str]:
        """Normalize heading path from parser output."""
        heading_path = list(getattr(section, "heading_path", []) or [])
        heading = getattr(section, "heading", None)
        if heading and heading not in heading_path:
            heading_path.append(heading)
        return heading_path

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return count_tokens(text)

    def _create_chunk(
        self,
        content: str,
        section: DocumentSection,
        source: str,
        *,
        record_type: str,
        parent_id: str | None = None,
    ) -> Chunk:
        """Create a chunk with hierarchy and retrieval metadata."""
        token_count = self._estimate_tokens(content)
        heading_path = self._heading_path(section)

        metadata = ChunkMetadata(
            source=source,
            page=getattr(section, "page", None),
            page_end=getattr(section, "page_end", None) or getattr(section, "page", None),
            heading=heading_path[-1] if heading_path else getattr(section, "heading", None),
            heading_path=heading_path,
            section_type=getattr(section, "section_type", "paragraph"),
            record_type=record_type,
            parent_id=parent_id,
            char_count=len(content),
            token_count=token_count,
        )

        return Chunk(id=str(uuid.uuid4()), content=content, metadata=metadata)

    def _update_chunk_indices(self, chunks: list[Chunk]) -> None:
        """Update chunk_index and total_chunks for all chunks."""
        for i, chunk in enumerate(chunks):
            chunk.metadata.chunk_index = i
            chunk.metadata.total_chunks = len(chunks)

    def _child_token_budget(self, max_tokens: int) -> int:
        """Pick a smaller child size for precise vector search."""
        if max_tokens <= 160:
            return max_tokens
        return max(120, max_tokens // 2)
