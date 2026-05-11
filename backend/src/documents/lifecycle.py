"""RAG document lifecycle helpers for upload ingestion."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.core.validators import (
    ValidationError,
    sanitize_metadata,
    validate_file_upload,
    validate_json_size,
)
from src.documents.models import Document


class DocumentUploadValidationError(ValueError):
    """Raised when uploaded document metadata or bytes are invalid."""


@dataclass(frozen=True)
class ValidatedUpload:
    """Validated upload bytes and metadata."""

    filename: str
    content: bytes
    file_type: str
    metadata: dict[str, Any]


class DocumentLifecycle:
    """Owns parse → chunk → vector-store ingestion for RAG documents."""

    def __init__(self, parser: Any, chunker: Any, vector_store: Any) -> None:
        self.parser = parser
        self.chunker = chunker
        self.vector_store = vector_store

    async def ingest_upload(
        self,
        upload: ValidatedUpload,
        *,
        device_id: str,
        session_id: str,
    ) -> Document:
        """Parse, chunk, and store one uploaded document."""
        sections = self.parser.parse_from_bytes(upload.content, upload.file_type)
        if not sections:
            raise DocumentUploadValidationError("No content extracted from file")

        chunks = self.chunker.chunk(sections, source=upload.filename)
        document = Document(
            id=str(uuid4()),
            filename=upload.filename,
            file_type=upload.file_type,
            upload_time=datetime.now(tz=UTC),
            chunks=chunks,
            total_tokens=sum(c.metadata.token_count for c in chunks),
            metadata=upload.metadata,
        )

        await self.vector_store.add_document(
            document,
            device_id=device_id,
            session_id=session_id,
        )
        return document


def parse_upload_metadata(metadata_json: str) -> dict[str, Any]:
    """Validate, parse, and sanitize upload metadata JSON."""
    is_valid, error = validate_json_size(metadata_json, max_size_kb=10)
    if not is_valid:
        raise DocumentUploadValidationError(f"Invalid metadata: {error}")

    try:
        parsed = json.loads(metadata_json)
    except json.JSONDecodeError as e:
        raise DocumentUploadValidationError(f"Invalid metadata JSON: {e}") from e

    if not isinstance(parsed, dict):
        raise DocumentUploadValidationError("Invalid metadata JSON: expected object")

    return sanitize_metadata(parsed)


def validate_upload_bytes(
    *,
    filename: str | None,
    content: bytes,
    declared_mime_type: str | None,
    metadata: dict[str, Any],
) -> ValidatedUpload:
    """Validate uploaded bytes and return normalized upload data."""
    safe_filename = filename or "unknown"
    if safe_filename in (".", "", ".."):
        raise DocumentUploadValidationError("Invalid filename")

    try:
        is_valid, error, file_metadata = validate_file_upload(
            filename=safe_filename,
            content=content,
            declared_mime_type=declared_mime_type,
        )
    except ValidationError as e:
        raise DocumentUploadValidationError("잘못된 요청 형식입니다.") from e

    if not is_valid:
        raise DocumentUploadValidationError(error or "Invalid file upload")

    file_type = file_metadata.get("detected_type") or file_metadata.get("extension")
    if not file_type:
        raise DocumentUploadValidationError("Could not determine file type")

    return ValidatedUpload(
        filename=safe_filename,
        content=content,
        file_type=str(file_type),
        metadata=metadata,
    )
