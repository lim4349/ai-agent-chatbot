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


class FakeQueryIndex:
    def query(self, vector, top_k, namespace, filter, include_metadata):
        self.query_args = {
            "vector": vector,
            "top_k": top_k,
            "namespace": namespace,
            "filter": filter,
            "include_metadata": include_metadata,
        }
        return type(
            "QueryResponse",
            (),
            {
                "matches": [
                    type(
                        "Match",
                        (),
                        {
                            "score": 0.99,
                            "metadata": {
                                "record_type": "parent",
                                "document_id": "doc-1",
                                "text": "large parent context",
                            },
                        },
                    )(),
                    type(
                        "Match",
                        (),
                        {
                            "score": 0.91,
                            "metadata": {
                                "record_type": "child",
                                "document_id": "doc-1",
                                "text": "precise child match",
                            },
                        },
                    )(),
                ]
            },
        )()


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
    assert parent["values"] == [1.0, 0.0, 0.0]
    assert child["values"] == [1.0, 2.0, 3.0]
    assert child["metadata"]["record_type"] == "child"
    assert child["metadata"]["parent_id"] == "parent-1"
    assert child["metadata"]["heading_path_text"] == "Benefits"
    assert child["metadata"]["parse_table_count"] == 1
    assert child["metadata"]["parse_warnings"] == ["Page 2 has little extractable text"]
    assert store._index.upserts[0]["namespace"] == "device_device-1"


@pytest.mark.asyncio
async def test_search_skips_parent_context_records():
    store = PineconeVectorStore(
        api_key=None,
        embedding_generator=FakeEmbeddingGenerator(),
    )
    store._index = FakeQueryIndex()

    results = await store.search("benefit amount", top_k=1, device_id="device-1")

    assert len(results) == 1
    assert results[0].chunk_content == "precise child match"
    assert store._index.query_args["top_k"] == 4
