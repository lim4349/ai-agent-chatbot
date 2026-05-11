"""Tests for RAG document lifecycle helpers."""

import pytest

from src.documents.lifecycle import (
    DocumentLifecycle,
    DocumentUploadValidationError,
    parse_upload_metadata,
    validate_upload_bytes,
)


def test_parse_upload_metadata_sanitizes_object():
    result = parse_upload_metadata('{"source": "unit", "nested": {"value": "ok"}}')

    assert result["source"] == "unit"
    assert result["nested"]["value"] == "ok"


def test_parse_upload_metadata_rejects_non_object_json():
    with pytest.raises(DocumentUploadValidationError):
        parse_upload_metadata('["not", "object"]')


class FakeParser:
    def parse_from_bytes(self, content, file_type):
        from src.documents.parser import DocumentSection

        return [DocumentSection(content=content.decode(), section_type="paragraph")]


class FakeChunker:
    def chunk(self, sections, source=""):
        from src.documents.models import Chunk, ChunkMetadata

        return [
            Chunk(
                id="chunk-1",
                content=sections[0].content,
                metadata=ChunkMetadata(source=source, token_count=3),
            )
        ]


class FakeVectorStore:
    def __init__(self):
        self.calls = []

    async def add_document(self, document, device_id=None, session_id=None):
        self.calls.append(
            {"document": document, "device_id": device_id, "session_id": session_id}
        )


@pytest.mark.asyncio
async def test_document_lifecycle_ingests_validated_upload():
    vector_store = FakeVectorStore()
    lifecycle = DocumentLifecycle(
        parser=FakeParser(),
        chunker=FakeChunker(),
        vector_store=vector_store,
    )
    upload = validate_upload_bytes(
        filename="notes.txt",
        content=b"hello rag",
        declared_mime_type="text/plain",
        metadata={"source": "unit"},
    )

    document = await lifecycle.ingest_upload(
        upload,
        device_id="device-1",
        session_id="session-1",
    )

    assert document.filename == "notes.txt"
    assert document.total_tokens == 3
    assert vector_store.calls[0]["device_id"] == "device-1"
    assert vector_store.calls[0]["session_id"] == "session-1"
