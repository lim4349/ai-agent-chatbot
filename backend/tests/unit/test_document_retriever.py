"""Tests for document retrieval context hydration."""

import pytest

from src.documents.pinecone_store import SearchResult
from src.documents.retriever_impl import PineconeDocumentRetriever


class FakeVectorStore:
    async def search(self, query, top_k=5, filters=None, device_id=None):
        return [
            SearchResult(
                chunk_content="Wedding benefit amount is 500000 KRW.",
                score=0.91,
                document_id="doc-1",
                metadata={
                    "document_id": "doc-1",
                    "chunk_id": "child-1",
                    "record_type": "child",
                    "parent_id": "parent-1",
                    "child_id": "child-1",
                    "filename": "policy.md",
                    "file_type": "md",
                    "source": "policy.md",
                    "page": 3,
                    "page_end": 3,
                    "heading": "Benefits",
                    "heading_path": ["Policy", "Benefits"],
                    "heading_path_text": "Policy > Benefits",
                    "section_type": "paragraph",
                    "chunk_index": 1,
                    "total_chunks": 2,
                },
            )
        ]

    async def get_chunk(self, *, document_id, chunk_id, device_id=None):
        return SearchResult(
            chunk_content=(
                "Section: Policy > Benefits\n\n"
                "Wedding benefit amount is 500000 KRW. Funeral benefit amount is 300000 KRW."
            ),
            score=0,
            document_id=document_id,
            metadata={
                "document_id": document_id,
                "chunk_id": chunk_id,
                "record_type": "parent",
                "page": 3,
                "page_end": 4,
            },
        )


@pytest.mark.asyncio
async def test_retriever_hydrates_parent_context_from_child_hit():
    retriever = PineconeDocumentRetriever(
        vector_store=FakeVectorStore(),
        chunker=None,
        parser=None,
    )

    results = await retriever.retrieve(
        "How much is the wedding benefit?",
        session_id="session-1",
        device_id="device-1",
    )

    assert len(results) == 1
    assert "Funeral benefit" in results[0]["content"]
    assert results[0]["matched_excerpt"] == "Wedding benefit amount is 500000 KRW."
    assert results[0]["metadata"]["parent_id"] == "parent-1"
    assert results[0]["metadata"]["heading_path"] == ["Policy", "Benefits"]
    assert results[0]["metadata"]["page_end"] == 4
