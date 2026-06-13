"""Document models for the AI Agent Chatbot backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ChunkMetadata:
    """Metadata for a document chunk."""

    source: str
    page: int | None = None
    page_end: int | None = None
    heading: str | None = None
    heading_path: list[str] = field(default_factory=list)
    section_type: str = "paragraph"
    record_type: str = "chunk"
    parent_id: str | None = None
    child_id: str | None = None
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


@dataclass
class Document:
    """A parsed document with its chunks."""

    id: str
    filename: str
    file_type: str
    upload_time: datetime
    chunks: list[Chunk] = field(default_factory=list)
    total_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseQuality:
    """Quality summary for parsed RAG Document content."""

    page_count: int = 0
    table_count: int = 0
    element_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable parse quality summary."""
        return {
            "page_count": self.page_count,
            "table_count": self.table_count,
            "element_count": self.element_count,
            "warnings": list(self.warnings),
        }


@dataclass
class ParsedElement:
    """One layout-aware parsed document element."""

    content: str
    page: int | None = None
    page_end: int | None = None
    heading: str | None = None
    heading_path: list[str] = field(default_factory=list)
    section_type: str = "paragraph"
    bbox: tuple[float, float, float, float] | None = None


@dataclass
class ParsedDocument:
    """Canonical parsed document used before chunking."""

    elements: list[ParsedElement]
    markdown: str
    quality: ParseQuality = field(default_factory=ParseQuality)
    metadata: dict[str, Any] = field(default_factory=dict)
