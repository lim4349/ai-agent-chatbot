"""Optional smoke tests for the real Pinecone RAG document lifecycle."""

import asyncio
import os
from uuid import uuid4

import pytest

from src.documents.chunker import StructureAwareChunker
from src.documents.embeddings import PineconeInferenceEmbedding
from src.documents.lifecycle import DocumentLifecycle, validate_upload_bytes
from src.documents.parser import DocumentParser
from src.documents.pinecone_store import PineconeVectorStore


@pytest.mark.asyncio
async def test_pinecone_document_lifecycle_smoke():
    """Validate upload -> list -> retrieve -> delete against a real Pinecone adapter."""
    api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX_NAME")
    if not api_key or not index_name:
        pytest.skip("PINECONE_API_KEY and PINECONE_INDEX_NAME are required")

    vector_store = PineconeVectorStore(
        api_key=api_key,
        index_name=index_name,
        embedding_generator=PineconeInferenceEmbedding(api_key=api_key),
    )
    if not vector_store._index:
        pytest.skip("Pinecone index is not available")

    lifecycle = DocumentLifecycle(
        parser=DocumentParser(),
        chunker=StructureAwareChunker(max_tokens=120, overlap_tokens=10),
        vector_store=vector_store,
    )
    device_id = f"smoke-device-{uuid4()}"
    session_id = f"smoke-session-{uuid4()}"
    upload = validate_upload_bytes(
        filename="smoke.txt",
        content=b"Smoke lifecycle policy: uploaded documents must stay scoped to one session.",
        declared_mime_type="text/plain",
        metadata={"source": "smoke"},
    )

    document = await lifecycle.ingest_upload(upload, device_id=device_id, session_id=session_id)

    try:
        assert await lifecycle.has_documents(device_id=device_id, session_id=session_id) is True
        assert await lifecycle.list_documents(device_id=device_id, session_id="other") == []

        documents = await lifecycle.list_documents(device_id=device_id, session_id=session_id)
        assert [doc.document_id for doc in documents] == [document.id]

        results = []
        for _ in range(5):
            results = await vector_store.search(
                query="What must stay scoped to one session?",
                top_k=3,
                filters={"session_id": session_id},
                device_id=device_id,
            )
            if results:
                break
            await asyncio.sleep(2)

        assert results
        assert results[0].metadata["session_id"] == session_id
    finally:
        await lifecycle.delete_document(
            document_id=document.id,
            device_id=device_id,
            session_id=session_id,
        )

    assert await lifecycle.list_documents(device_id=device_id, session_id=session_id) == []
