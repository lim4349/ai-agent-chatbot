"""Tests for hierarchy-aware parent-child chunking."""

from src.documents.chunker import StructureAwareChunker
from src.documents.parser import DocumentSection


def test_chunker_emits_parent_and_child_with_heading_context():
    chunker = StructureAwareChunker(max_tokens=80, overlap_tokens=10)
    chunks = chunker.chunk(
        [
            DocumentSection(
                content="Marriage benefit pays 500000 KRW to eligible employees.",
                heading="Benefits",
                heading_path=["Policy", "Benefits"],
                section_type="paragraph",
                page=2,
            )
        ],
        source="policy.md",
    )

    parent = next(chunk for chunk in chunks if chunk.metadata.record_type == "parent")
    child = next(chunk for chunk in chunks if chunk.metadata.record_type == "child")

    assert parent.content.startswith("Section: Policy > Benefits")
    assert child.metadata.parent_id == parent.id
    assert child.metadata.child_id == child.id
    assert child.metadata.heading_path == ["Policy", "Benefits"]
    assert child.metadata.page == 2


def test_chunker_repeats_table_header_for_child_chunks():
    chunker = StructureAwareChunker(max_tokens=50, overlap_tokens=0)
    chunks = chunker.chunk(
        [
            DocumentSection(
                content=(
                    "| Item | Amount |\n"
                    "| --- | --- |\n"
                    "| Wedding | 500000 |\n"
                    "| Funeral | 300000 |\n"
                    "| Birth | 200000 |"
                ),
                heading_path=["Benefits"],
                section_type="table",
            )
        ],
        source="policy.md",
    )

    child_chunks = [chunk for chunk in chunks if chunk.metadata.record_type == "child"]

    assert child_chunks
    assert all("| Item | Amount |" in chunk.content for chunk in child_chunks)
    assert all(chunk.metadata.section_type == "table" for chunk in child_chunks)
