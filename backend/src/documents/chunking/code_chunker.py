"""Code-aware chunker that respects function/class boundaries."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.documents.parser import DocumentSection

from src.documents.chunking.base import BaseChunker, Chunk


class CodeDocumentChunker(BaseChunker):
    """Chunker for code documents that respects function/class boundaries.

    This chunker analyzes code structure and tries to keep related code
    (functions, classes, methods) together when possible.
    """

    # Language-specific patterns for code structure detection
    PATTERNS = {
        "python": {
            "function": r"def\s+\w+\s*\(.*?\):",
            "class": r"class\s+\w+.*?:",
            "decorator": r"@\w+",
        },
        "javascript": {
            "function": r"(?:function\s+\w+\s*\(.*?\)|const\s+\w+\s*=.*?=>|\w+\s*\(.*?\)\s*=>)",
            "class": r"class\s+\w+.*?{",
            "method": r"async\s+\w+\s*\(.*?\)|\w+\s*\(.*?\)[^{]*{",
        },
        "java": {
            "class": r"(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:final\s+)?class\s+\w+",
            "method": r"(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?\w+\s+\w+\s*\(.*?\)",
            "interface": r"interface\s+\w+",
        },
        "go": {
            "function": r"func\s+(?:\(\*\w+\s*)?\w+\s*)\(.*?\)",
            "interface": r"type\s+\w+\s+interface",
        },
        "rust": {
            "function": r"fn\s+\w+\s*\(.*?\)",
            "struct": r"struct\s+\w+",
            "impl": r"impl\s+\w+\s+for",
        },
    }

    # File extension to language mapping
    EXTENSION_MAP = {
        "py": "python",
        "pyi": "python",
        "js": "javascript",
        "jsx": "javascript",
        "ts": "javascript",
        "tsx": "javascript",
        "java": "java",
        "go": "go",
        "rs": "rust",
        "cpp": "cpp",
        "c": "c",
        "h": "c",
        "cs": "csharp",
        "php": "php",
        "rb": "ruby",
        "swift": "swift",
        "kt": "kotlin",
    }

    @override
    def chunk(
        self,
        sections: Sequence[DocumentSection],
        source: str = "",
    ) -> list[Chunk]:
        """Chunk code sections respecting structure boundaries."""
        chunks: list[Chunk] = []

        for section in sections:
            section_chunks = self._chunk_code_section(section, source)
            chunks.extend(section_chunks)

        self._update_chunk_indices(chunks)
        return chunks

    def _detect_language(self, source: str) -> str:
        """Detect programming language from file extension."""
        ext = source.rsplit(".", 1)[-1].lower() if "." in source else ""
        return self.EXTENSION_MAP.get(ext, "python")

    def _chunk_code_section(
        self,
        section: DocumentSection,
        source: str,
    ) -> list[Chunk]:
        """Chunk a single code section."""
        language = self._detect_language(source)
        content = section.content

        # If content is small enough, keep as one chunk
        if self._estimate_tokens(content) <= self.max_tokens:
            return [self._create_chunk(content, section, source, language=language)]

        # Try to split by code structure
        return self._split_by_structure(content, section, source, language)

    def _split_by_structure(
        self,
        content: str,
        section: DocumentSection,
        source: str,
        language: str,
    ) -> list[Chunk]:
        """Split code by structure boundaries (functions, classes)."""
        patterns = self.PATTERNS.get(language, self.PATTERNS["python"])

        # Find all structure boundaries
        boundaries = self._find_boundaries(content, patterns)

        if not boundaries:
            # No clear structure found, fall back to line-based splitting
            return self._split_by_lines(content, section, source, language)

        # Group content by boundaries
        chunks: list[Chunk] = []
        current_lines: list[str] = []

        for idx, boundary in enumerate(boundaries):
            current_lines.append(boundary["full_line"])

            # Check if we've accumulated enough content
            current_text = "\n".join(current_lines)
            if self._estimate_tokens(current_text) >= self.max_tokens or idx == len(boundaries) - 1:
                # Create chunk
                chunk_text = "\n".join(current_lines)
                chunks.append(self._create_chunk(chunk_text, section, source, language=language))

                # Start new chunk with overlap (last few lines)
                overlap_count = min(3, len(current_lines))
                current_lines = current_lines[-overlap_count:]

        return (
            chunks if chunks else [self._create_chunk(content, section, source, language=language)]
        )

    def _find_boundaries(self, content: str, patterns: dict[str, str]) -> list[dict]:
        """Find code structure boundaries with their positions."""
        boundaries: list[dict] = []
        lines = content.split("\n")

        # Combine all pattern types
        all_patterns = "|".join(f"(?P<{name}>{pattern})" for name, pattern in patterns.items())

        for line_no, line in enumerate(lines):
            match = re.search(all_patterns, line.strip())
            if match:
                # Determine which pattern matched
                for name, value in match.groupdict().items():
                    if value:
                        boundaries.append(
                            {
                                "type": name,
                                "line_no": line_no,
                                "line": line,
                                "full_line": line,
                                "indent": len(line) - len(line.lstrip()),
                            }
                        )
                        break
            else:
                # Keep track of non-boundary lines for context
                if boundaries:
                    boundaries[-1]["full_line"] += "\n" + line

        return boundaries

    def _split_by_lines(
        self,
        content: str,
        section: DocumentSection,
        source: str,
        language: str,
    ) -> list[Chunk]:
        """Fall back to line-based splitting when no clear structure."""
        lines = content.split("\n")
        chunks: list[Chunk] = []
        current_lines: list[str] = []
        current_tokens = 0

        for line in lines:
            line_tokens = self._estimate_tokens(line + "\n")

            # Check if adding this line would exceed limit
            if current_tokens + line_tokens > self.max_tokens and current_lines:
                # Create chunk from accumulated lines
                chunk_text = "\n".join(current_lines)
                chunks.append(self._create_chunk(chunk_text, section, source, language=language))

                # Start new chunk with overlap lines
                overlap_count = min(5, len(current_lines))
                current_lines = current_lines[-overlap_count:]
                current_tokens = sum(self._estimate_tokens(line + "\n") for line in current_lines)

            current_lines.append(line)
            current_tokens += line_tokens

        # Don't forget the last chunk
        if current_lines:
            chunk_text = "\n".join(current_lines)
            chunks.append(self._create_chunk(chunk_text, section, source, language=language))

        return chunks
