"""Layout-aware document parser supporting multiple file formats."""

from __future__ import annotations

import csv
import json
import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.documents.models import ParsedDocument, ParsedElement, ParseQuality


@dataclass
class DocumentSection(ParsedElement):
    """A section of a parsed document.

    Kept as the parser's compatibility surface for existing chunkers and tests.
    """


class DocumentParser:
    """Parser for multiple document formats."""

    def parse_document_from_bytes(self, content: bytes, file_type: str) -> ParsedDocument:
        """Parse document bytes into canonical layout-aware content."""
        self._reset_parse_state()
        file_type = file_type.lower()

        if file_type in ("txt", "md", "csv", "json"):
            text = self._decode_bytes(content)
            if file_type == "txt":
                sections = self._parse_text_content(text)
            elif file_type == "md":
                sections = self._parse_md_content(text)
            elif file_type == "csv":
                sections = self._parse_csv_content(text)
            else:
                sections = self._parse_json_content(text)
            return self._build_parsed_document(sections)

        import os

        suffix = f".{file_type}"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            return self.parse_document(tmp_path, file_type)
        finally:
            os.unlink(tmp_path)

    def parse_from_bytes(self, content: bytes, file_type: str) -> list[DocumentSection]:
        """Parse document from bytes and return chunker-compatible sections."""
        return list(self.parse_document_from_bytes(content, file_type).elements)

    def parse_document(self, file_path: str, file_type: str) -> ParsedDocument:
        """Parse a document path into canonical layout-aware content."""
        self._reset_parse_state()
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_type = file_type.lower()
        if file_type == "pdf":
            sections = self._parse_pdf(path)
        elif file_type == "docx":
            sections = self._parse_docx(path)
        elif file_type == "txt":
            sections = self._parse_txt(path)
        elif file_type == "md":
            sections = self._parse_md(path)
        elif file_type == "csv":
            sections = self._parse_csv(path)
        elif file_type == "json":
            sections = self._parse_json(path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        return self._build_parsed_document(sections)

    def parse(self, file_path: str, file_type: str) -> list[DocumentSection]:
        """Parse a document path and return chunker-compatible sections."""
        return list(self.parse_document(file_path, file_type).elements)

    def _reset_parse_state(self) -> None:
        self._parse_warnings: list[str] = []
        self._page_count = 0

    def _decode_bytes(self, content: bytes) -> str:
        """Decode bytes to string trying common encodings."""
        for encoding in ("utf-8", "cp949", "euc-kr", "latin-1"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue

        return content.decode("utf-8", errors="replace")

    def _detect_encoding(self, path: Path) -> str:
        """Detect file encoding trying common encodings."""
        for encoding in ("utf-8", "cp949", "euc-kr", "latin-1"):
            try:
                with open(path, encoding=encoding) as f:
                    f.read()
                return encoding
            except UnicodeDecodeError:
                continue

        return "utf-8"

    def _parse_text_content(self, text: str) -> list[DocumentSection]:
        """Parse plain text content."""
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        return [DocumentSection(content=para, section_type="paragraph") for para in paragraphs]

    def _parse_md_content(self, text: str) -> list[DocumentSection]:
        """Parse Markdown content preserving headings, tables, and code blocks."""
        sections: list[DocumentSection] = []
        lines = text.splitlines()
        heading_stack: list[str] = []
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                heading_stack = heading_stack[: level - 1] + [heading_text]
                sections.append(
                    DocumentSection(
                        content=heading_text,
                        heading=heading_text,
                        heading_path=list(heading_stack),
                        section_type="heading",
                    )
                )
                i += 1
                continue

            if stripped.startswith("```"):
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                if i < len(lines):
                    i += 1
                code_content = "\n".join(code_lines).strip()
                if code_content:
                    sections.append(
                        DocumentSection(
                            content=code_content,
                            heading=self._current_heading(heading_stack),
                            heading_path=list(heading_stack),
                            section_type="code",
                        )
                    )
                continue

            if self._looks_like_table_start(lines, i):
                table_lines = []
                while i < len(lines) and "|" in lines[i]:
                    if lines[i].strip():
                        table_lines.append(lines[i].strip())
                    i += 1
                if table_lines:
                    sections.append(
                        DocumentSection(
                            content="\n".join(table_lines),
                            heading=self._current_heading(heading_stack),
                            heading_path=list(heading_stack),
                            section_type="table",
                        )
                    )
                continue

            if stripped:
                para_lines = [stripped]
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if (
                        not next_line
                        or next_line.startswith("#")
                        or next_line.startswith("```")
                        or self._looks_like_table_start(lines, i)
                    ):
                        break
                    para_lines.append(next_line)
                    i += 1
                sections.append(
                    DocumentSection(
                        content=" ".join(para_lines),
                        heading=self._current_heading(heading_stack),
                        heading_path=list(heading_stack),
                        section_type="paragraph",
                    )
                )
                continue

            i += 1

        return sections

    def _parse_csv_content(self, text: str) -> list[DocumentSection]:
        """Parse CSV content as one Markdown table section."""
        import io

        reader = csv.reader(io.StringIO(text))
        rows = [row for row in reader if any(cell.strip() for cell in row)]
        if not rows:
            return []

        return [DocumentSection(content=self._rows_to_markdown_table(rows), section_type="table")]

    def _parse_json_content(self, text: str) -> list[DocumentSection]:
        """Parse JSON content into readable structured text."""
        data = json.loads(text)
        formatted = json.dumps(data, ensure_ascii=False, indent=2)
        return [DocumentSection(content=formatted, section_type="code")]

    def _parse_pdf(self, path: Path) -> list[DocumentSection]:
        """Parse PDF file using pdfplumber layout signals."""
        try:
            import pdfplumber

            logging.getLogger("pdfminer").setLevel(logging.ERROR)
            logging.getLogger("pdfplumber").setLevel(logging.ERROR)
        except ImportError as err:
            raise ImportError(
                "pdfplumber is required for PDF parsing. Install with: pip install pdfplumber"
            ) from err

        sections: list[DocumentSection] = []
        with pdfplumber.open(path) as pdf:
            self._page_count = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                page_sections = self._parse_pdf_page_text(page_text, page_num)
                sections.extend(page_sections)

                for table in page.extract_tables() or []:
                    markdown_table = self._rows_to_markdown_table(table)
                    if markdown_table:
                        sections.append(
                            DocumentSection(
                                content=markdown_table,
                                page=page_num,
                                page_end=page_num,
                                heading=page_sections[-1].heading if page_sections else None,
                                heading_path=(
                                    list(page_sections[-1].heading_path) if page_sections else []
                                ),
                                section_type="table",
                            )
                        )

                if not page_text.strip() and not page.extract_tables():
                    self._parse_warnings.append(
                        f"Page {page_num} has little extractable text; scanned content may need OCR."
                    )

        if self._page_count and not sections:
            self._parse_warnings.append(
                "No extractable text was found. The document may be scanned or image-only."
            )

        return sections

    def _parse_pdf_page_text(self, text: str, page_num: int) -> list[DocumentSection]:
        """Convert extracted page text into paragraph sections with light heading hints."""
        sections: list[DocumentSection] = []
        heading_stack: list[str] = []

        for block in [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue

            if len(lines) == 1 and self._looks_like_heading(lines[0]):
                heading = lines[0]
                heading_stack = [heading]
                sections.append(
                    DocumentSection(
                        content=heading,
                        page=page_num,
                        page_end=page_num,
                        heading=heading,
                        heading_path=list(heading_stack),
                        section_type="heading",
                    )
                )
                continue

            sections.append(
                DocumentSection(
                    content=" ".join(lines),
                    page=page_num,
                    page_end=page_num,
                    heading=self._current_heading(heading_stack),
                    heading_path=list(heading_stack),
                    section_type="paragraph",
                )
            )

        return sections

    def _parse_docx(self, path: Path) -> list[DocumentSection]:
        """Parse DOCX file preserving paragraph/table order and heading hierarchy."""
        try:
            from docx import Document as DocxDocument
            from docx.table import Table
            from docx.text.paragraph import Paragraph
        except ImportError as err:
            raise ImportError(
                "python-docx is required for DOCX parsing. Install with: pip install python-docx"
            ) from err

        doc = DocxDocument(path)
        sections: list[DocumentSection] = []
        heading_stack: list[str] = []

        for child in doc.element.body.iterchildren():
            if child.tag.endswith("}p"):
                para = Paragraph(child, doc)
                text = para.text.strip()
                if not text:
                    continue

                heading_level = self._docx_heading_level(para.style.name)
                if heading_level:
                    heading_stack = heading_stack[: heading_level - 1] + [text]
                    sections.append(
                        DocumentSection(
                            content=text,
                            heading=text,
                            heading_path=list(heading_stack),
                            section_type="heading",
                        )
                    )
                else:
                    sections.append(
                        DocumentSection(
                            content=text,
                            heading=self._current_heading(heading_stack),
                            heading_path=list(heading_stack),
                            section_type="paragraph",
                        )
                    )
            elif child.tag.endswith("}tbl"):
                table = Table(child, doc)
                rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
                markdown_table = self._rows_to_markdown_table(rows)
                if markdown_table:
                    sections.append(
                        DocumentSection(
                            content=markdown_table,
                            heading=self._current_heading(heading_stack),
                            heading_path=list(heading_stack),
                            section_type="table",
                        )
                    )

        return sections

    def _parse_txt(self, path: Path) -> list[DocumentSection]:
        """Parse plain text file with encoding detection."""
        with open(path, encoding=self._detect_encoding(path)) as f:
            return self._parse_text_content(f.read())

    def _parse_md(self, path: Path) -> list[DocumentSection]:
        """Parse Markdown file preserving structure."""
        with open(path, encoding=self._detect_encoding(path)) as f:
            return self._parse_md_content(f.read())

    def _parse_csv(self, path: Path) -> list[DocumentSection]:
        """Parse CSV file preserving table structure."""
        with open(path, encoding=self._detect_encoding(path), newline="") as f:
            return self._parse_csv_content(f.read())

    def _parse_json(self, path: Path) -> list[DocumentSection]:
        """Parse JSON file preserving structured content."""
        with open(path, encoding=self._detect_encoding(path)) as f:
            return self._parse_json_content(f.read())

    def _build_parsed_document(self, sections: list[DocumentSection]) -> ParsedDocument:
        """Build the canonical parsed document wrapper."""
        table_count = sum(1 for section in sections if section.section_type == "table")
        page_numbers = [section.page for section in sections if section.page is not None]
        page_count = self._page_count or (max(page_numbers) if page_numbers else 0)
        quality = ParseQuality(
            page_count=page_count,
            table_count=table_count,
            element_count=len(sections),
            warnings=list(dict.fromkeys(self._parse_warnings)),
        )
        return ParsedDocument(
            elements=list(sections),
            markdown=self._sections_to_markdown(sections),
            quality=quality,
        )

    def _sections_to_markdown(self, sections: list[DocumentSection]) -> str:
        """Render parsed sections into a Markdown-like canonical text."""
        rendered: list[str] = []
        for section in sections:
            if section.section_type == "heading":
                level = min(max(len(section.heading_path), 1), 6)
                rendered.append(f"{'#' * level} {section.content}")
            elif section.section_type == "code":
                rendered.append(f"```\n{section.content}\n```")
            else:
                rendered.append(section.content)
        return "\n\n".join(part for part in rendered if part.strip())

    def _looks_like_table_start(self, lines: list[str], index: int) -> bool:
        """Return whether a Markdown table appears to start at index."""
        if index + 1 >= len(lines):
            return False
        current = lines[index].strip()
        next_line = lines[index + 1].strip()
        return "|" in current and bool(re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", next_line))

    def _looks_like_heading(self, text: str) -> bool:
        """Lightweight heading heuristic for extracted PDF text."""
        if len(text) > 80 or text.endswith((".", "?", "!", "다", "요")):
            return False
        return bool(re.match(r"^(\d+(\.\d+)*\.?\s+|[A-Z][A-Z\s]{3,}$|제\s*\d+\s*[장조])", text))

    def _docx_heading_level(self, style_name: str) -> int | None:
        """Extract a heading level from a python-docx style name."""
        match = re.match(r"Heading\s+([1-6])", style_name or "")
        if not match:
            return None
        return int(match.group(1))

    def _rows_to_markdown_table(self, rows: list[list[Any]]) -> str:
        """Convert table rows into Markdown while preserving row/column structure."""
        cleaned_rows = [
            [self._clean_table_cell(cell) for cell in row]
            for row in rows
            if row and any(str(cell or "").strip() for cell in row)
        ]
        if not cleaned_rows:
            return ""

        width = max(len(row) for row in cleaned_rows)
        normalized = [row + [""] * (width - len(row)) for row in cleaned_rows]
        header = normalized[0]
        separator = ["---"] * width
        body = normalized[1:] or [[""] * width]

        table_lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(separator) + " |",
        ]
        table_lines.extend("| " + " | ".join(row) + " |" for row in body)
        return "\n".join(table_lines)

    def _clean_table_cell(self, cell: Any) -> str:
        """Normalize a table cell for Markdown output."""
        return str(cell or "").replace("\n", " ").replace("|", "\\|").strip()

    def _current_heading(self, heading_stack: list[str]) -> str | None:
        """Return the active leaf heading."""
        return heading_stack[-1] if heading_stack else None
