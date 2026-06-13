"""Tests for RAG document lifecycle helpers."""

from types import SimpleNamespace

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
        self.documents = {}

    async def add_document(self, document, device_id=None, session_id=None):
        self.calls.append(
            {"document": document, "device_id": device_id, "session_id": session_id}
        )
        self.documents[document.id] = {
            "document": document,
            "device_id": device_id,
            "session_id": session_id,
        }

    async def has_documents_for_session(self, device_id, session_id):
        return any(
            item["device_id"] == device_id and item["session_id"] == session_id
            for item in self.documents.values()
        )

    async def list_documents(self, device_id=None, session_id=None):
        return [
            doc_id
            for doc_id, item in self.documents.items()
            if item["device_id"] == device_id
            and (session_id is None or item["session_id"] == session_id)
        ]

    async def get_document_stats(self, document_id, device_id=None, session_id=None):
        item = self.documents.get(document_id)
        if not item or item["device_id"] != device_id:
            return None
        if session_id is not None and item["session_id"] != session_id:
            return None
        document = item["document"]
        return SimpleNamespace(
            document_id=document.id,
            filename=document.filename,
            file_type=document.file_type,
            upload_time=document.upload_time,
            chunk_count=len(document.chunks),
            total_tokens=document.total_tokens,
        )

    async def delete_document(self, document_id, device_id=None):
        item = self.documents.get(document_id)
        if item and item["device_id"] == device_id:
            del self.documents[document_id]
            return True
        return False


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


@pytest.mark.asyncio
async def test_document_lifecycle_lists_detects_and_deletes_session_documents():
    vector_store = FakeVectorStore()
    lifecycle = DocumentLifecycle(
        parser=FakeParser(),
        chunker=FakeChunker(),
        vector_store=vector_store,
    )
    upload = validate_upload_bytes(
        filename="policy.txt",
        content=b"retention policy",
        declared_mime_type="text/plain",
        metadata={"source": "unit"},
    )

    document = await lifecycle.ingest_upload(
        upload,
        device_id="device-1",
        session_id="session-1",
    )

    assert await lifecycle.has_documents(device_id="device-1", session_id="session-1") is True
    assert await lifecycle.has_documents(device_id="device-1", session_id="other") is False

    documents = await lifecycle.list_documents(device_id="device-1", session_id="session-1")
    assert [doc.document_id for doc in documents] == [document.id]
    assert documents[0].filename == "policy.txt"
    assert await lifecycle.list_documents(device_id="device-1", session_id="other") == []

    assert await lifecycle.delete_document(document_id=document.id, device_id="other") is False
    assert (
        await lifecycle.delete_document(
            document_id=document.id,
            device_id="device-1",
            session_id="other",
        )
        is False
    )
    assert await lifecycle.delete_document(document_id=document.id, device_id="device-1") is True
    assert await lifecycle.has_documents(device_id="device-1", session_id="session-1") is False
