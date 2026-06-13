"""Tests for Pinecone vector store document metadata handling."""

from datetime import UTC, datetime

import pytest

from src.documents.models import Chunk, ChunkMetadata, Document
from src.documents.pinecone_store import PineconeVectorStore


class FakeEmbeddingGenerator:
    dimension = 3

    async def generate(self, texts):
        return [[1.0, 2.0, 3.0] for _ in texts]

    async def embed_query(self, query):
        return [1.0, 2.0, 3.0]


class FakeIndex:
    def __init__(self):
        self.upserts = []

    def upsert(self, vectors, namespace):
        self.upserts.append({"vectors": vectors, "namespace": namespace})


@pytest.mark.asyncio
async def test_add_document_stores_parent_context_and_embeds_child_records():
    store = PineconeVectorStore(
        api_key=None,
        embedding_generator=FakeEmbeddingGenerator(),
    )
    store._index = FakeIndex()
    document = Document(
        id="doc-1",
        filename="policy.md",
        file_type="md",
        upload_time=datetime.now(tz=UTC),
        chunks=[
            Chunk(
                id="parent-1",
                content="Section: Benefits\n\nWedding benefit amount is 500000 KRW.",
                metadata=ChunkMetadata(
                    source="policy.md",
                    heading_path=["Benefits"],
                    record_type="parent",
                    parent_id="parent-1",
                    token_count=12,
                ),
            ),
            Chunk(
                id="child-1",
                content="Wedding benefit amount is 500000 KRW.",
                metadata=ChunkMetadata(
                    source="policy.md",
                    heading_path=["Benefits"],
                    record_type="child",
                    parent_id="parent-1",
                    child_id="child-1",
                    token_count=8,
                ),
            ),
        ],
        total_tokens=12,
        metadata={
            "parse_summary": {
                "page_count": 2,
                "table_count": 1,
                "element_count": 4,
                "warnings": ["Page 2 has little extractable text"],
                "parent_chunk_count": 1,
                "child_chunk_count": 1,
            }
        },
    )

    await store.add_document(document, device_id="device-1", session_id="session-1")

    vectors = store._index.upserts[0]["vectors"]
    by_id = {vector["id"]: vector for vector in vectors}

    parent = by_id["doc-1_parent-1"]
    child = by_id["doc-1_child-1"]
    assert parent["values"] == [0.0, 0.0, 0.0]
    assert child["values"] == [1.0, 2.0, 3.0]
    assert child["metadata"]["record_type"] == "child"
    assert child["metadata"]["parent_id"] == "parent-1"
    assert child["metadata"]["heading_path_text"] == "Benefits"
    assert child["metadata"]["parse_table_count"] == 1
    assert child["metadata"]["parse_warnings"] == ["Page 2 has little extractable text"]
    assert store._index.upserts[0]["namespace"] == "device_device-1"
