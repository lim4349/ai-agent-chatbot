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
