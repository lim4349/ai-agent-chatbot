"""Tests for layout-aware document parsing."""

from src.documents.parser import DocumentParser


def test_markdown_parser_preserves_heading_path_and_table():
    parser = DocumentParser()
    parsed = parser.parse_document_from_bytes(
        (
            b"# Policy\n\n"
            b"## Benefits\n\n"
            b"| Item | Amount |\n"
            b"| --- | --- |\n"
            b"| Wedding | 500000 |\n\n"
            b"Employees can request reimbursement."
        ),
        "md",
    )

    table = next(section for section in parsed.elements if section.section_type == "table")
    paragraph = next(section for section in parsed.elements if section.section_type == "paragraph")

    assert table.heading_path == ["Policy", "Benefits"]
    assert "| Item | Amount |" in table.content
    assert paragraph.heading_path == ["Policy", "Benefits"]
    assert parsed.quality.table_count == 1
    assert parsed.quality.element_count == 4
    assert "## Benefits" in parsed.markdown


def test_csv_parser_outputs_one_markdown_table():
    parser = DocumentParser()
    parsed = parser.parse_document_from_bytes(
        b"name,amount\nwedding,500000\n",
        "csv",
    )

    assert len(parsed.elements) == 1
    assert parsed.elements[0].section_type == "table"
    assert parsed.elements[0].content.splitlines() == [
        "| name | amount |",
        "| --- | --- |",
        "| wedding | 500000 |",
    ]
    assert parsed.quality.table_count == 1
