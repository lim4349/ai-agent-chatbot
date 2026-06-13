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
        parsed_document = None
        if hasattr(self.parser, "parse_document_from_bytes"):
            parsed_document = self.parser.parse_document_from_bytes(upload.content, upload.file_type)
            sections = parsed_document.elements
        else:
            sections = self.parser.parse_from_bytes(upload.content, upload.file_type)

        if not sections:
            raise DocumentUploadValidationError("No content extracted from file")

        chunks = self.chunker.chunk(sections, source=upload.filename)
        parent_chunks = [c for c in chunks if getattr(c.metadata, "record_type", "") == "parent"]
        child_chunks = [c for c in chunks if getattr(c.metadata, "record_type", "") == "child"]
        token_chunks = parent_chunks or chunks
        document_metadata = dict(upload.metadata)
        document_metadata["parse_summary"] = _parse_summary(parsed_document, len(parent_chunks), len(child_chunks))

        document = Document(
            id=str(uuid4()),
            filename=upload.filename,
            file_type=upload.file_type,
            upload_time=datetime.now(tz=UTC),
            chunks=chunks,
            total_tokens=sum(c.metadata.token_count for c in token_chunks),
            metadata=document_metadata,
        )

        await self.vector_store.add_document(
            document,
            device_id=device_id,
            session_id=session_id,
        )
        return document

    async def has_documents(self, *, device_id: str, session_id: str) -> bool:
        """Return whether the session has any stored RAG Documents."""
        return await self.vector_store.has_documents_for_session(device_id, session_id)

    async def list_documents(self, *, device_id: str, session_id: str | None = None) -> list[Any]:
        """List stored RAG Document stats for a device and optional session."""
        doc_ids = await self.vector_store.list_documents(device_id=device_id, session_id=session_id)
        documents = []
        for doc_id in doc_ids:
            stats = await self.vector_store.get_document_stats(
                doc_id,
                device_id=device_id,
                session_id=session_id,
            )
            if stats:
                documents.append(stats)
        return documents

    async def delete_document(
        self,
        *,
        document_id: str,
        device_id: str,
        session_id: str | None = None,
    ) -> bool:
        """Delete one RAG Document after verifying device and optional session ownership."""
        stats = await self.vector_store.get_document_stats(
            document_id,
            device_id=device_id,
            session_id=session_id,
        )
        if not stats:
            return False
        await self.vector_store.delete_document(document_id, device_id=device_id)
        return True

    async def delete_session_documents(self, *, device_id: str, session_id: str) -> int:
        """Delete all RAG Documents for a session."""
        return await self.vector_store.delete_session_documents(device_id, session_id)


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


def _parse_summary(parsed_document: Any, parent_count: int, child_count: int) -> dict[str, Any]:
    """Build a stable parse summary for API responses and vector metadata."""
    quality = getattr(parsed_document, "quality", None)
    if quality and hasattr(quality, "as_dict"):
        summary = quality.as_dict()
    else:
        summary = {
            "page_count": 0,
            "table_count": 0,
            "element_count": 0,
            "warnings": [],
        }

    summary["parent_chunk_count"] = parent_count
    summary["child_chunk_count"] = child_count
    return summary
