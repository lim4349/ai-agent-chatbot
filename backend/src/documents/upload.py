"""File upload handler for document processing."""

import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Protocol

from src.api.schemas import FileUploadResponse
from src.core.logging import get_logger

logger = get_logger(__name__)


class DocumentParser(Protocol):
    """Protocol for document parsers."""

    async def parse(self, file_path: str, file_type: str) -> str:
        """Parse a document and return its text content."""
        ...


class StructureAwareChunker(Protocol):
    """Protocol for document chunkers."""

    def chunk(self, text: str, metadata: dict | None = None) -> list[dict]:
        """Chunk text into smaller pieces with metadata."""
        ...


class DocumentVectorStore(Protocol):
    """Protocol for document vector stores."""

    async def add_documents(self, documents: list[dict]) -> None:
        """Add documents to the vector store."""
        ...

    async def delete_by_metadata(self, filter_dict: dict) -> None:
        """Delete documents matching metadata filter."""
        ...

    async def get_all_documents(self) -> list[dict]:
        """Get all documents with their metadata."""
        ...


class SimpleDocumentParser:
    """Simple parser for various document formats."""

    SUPPORTED_TYPES = {"pdf", "docx", "txt", "md", "csv", "json"}

    async def parse(self, file_path: str, file_type: str) -> str:
        """Parse a document based on its type.

        Args:
            file_path: Path to the file
            file_type: File extension without dot

        Returns:
            Extracted text content
        """
        file_type = file_type.lower()

        if file_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported file type: {file_type}")

        if file_type == "pdf":
            return await self._parse_pdf(file_path)
        elif file_type == "docx":
            return await self._parse_docx(file_path)
        elif file_type == "json":
            return await self._parse_json(file_path)
        elif file_type == "csv":
            return await self._parse_csv(file_path)
        else:  # txt, md
            return await self._parse_text(file_path)

    async def _parse_pdf(self, file_path: str) -> str:
        """Parse PDF file."""
        try:
            import PyPDF2

            text_parts = []
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text_parts.append(page.extract_text() or "")
            return "\n\n".join(text_parts)
        except ImportError as err:
            logger.error("PyPDF2 not installed")
            raise RuntimeError("PDF parsing requires PyPDF2. Install with: pip install PyPDF2") from err
        except Exception as e:
            logger.error("pdf_parse_failed", error=str(e))
            raise

    async def _parse_docx(self, file_path: str) -> str:
        """Parse DOCX file."""
        try:
            from docx import Document

            doc = Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphs)
        except ImportError as err:
            logger.error("python-docx not installed")
            raise RuntimeError("DOCX parsing requires python-docx. Install with: pip install python-docx") from err
        except Exception as e:
            logger.error("docx_parse_failed", error=str(e))
            raise

    async def _parse_json(self, file_path: str) -> str:
        """Parse JSON file."""
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            # Convert JSON to readable text
            return json.dumps(data, indent=2)
        except Exception as e:
            logger.error("json_parse_failed", error=str(e))
            raise

    async def _parse_csv(self, file_path: str) -> str:
        """Parse CSV file."""
        import csv

        try:
            text_parts = []
            with open(file_path, encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                for row in reader:
                    text_parts.append(" | ".join(row))
            return "\n".join(text_parts)
        except Exception as e:
            logger.error("csv_parse_failed", error=str(e))
            raise

    async def _parse_text(self, file_path: str) -> str:
        """Parse plain text file (txt, md)."""
        try:
            with open(file_path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error("text_parse_failed", error=str(e))
            raise


class SimpleChunker:
    """Simple structure-aware chunker for text documents."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """Initialize chunker.

        Args:
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Overlap between chunks in characters
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str, metadata: dict | None = None) -> list[dict]:
        """Chunk text into smaller pieces.

        Args:
            text: Text to chunk
            metadata: Metadata to attach to each chunk

        Returns:
            List of chunks with content and metadata
        """
        if not text:
            return []

        metadata = metadata or {}
        chunks = []

        # Split by paragraphs first (structure awareness)
        paragraphs = text.split("\n\n")
        current_chunk = []
        current_size = 0

        for _i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue

            para_size = len(para)

            # If adding this paragraph exceeds chunk size, save current chunk
            if current_size + para_size > self.chunk_size and current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                chunks.append({
                    "content": chunk_text,
                    "metadata": {
                        **metadata,
                        "chunk_index": len(chunks),
                    },
                })
                # Keep overlap paragraphs
                overlap_start = max(0, len(current_chunk) - 1)
                current_chunk = current_chunk[overlap_start:] + [para]
                current_size = sum(len(p) for p in current_chunk)
            else:
                current_chunk.append(para)
                current_size += para_size

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append({
                "content": chunk_text,
                "metadata": {
                    **metadata,
                    "chunk_index": len(chunks),
                },
            })

        return chunks


class FileUploadHandler:
    """Handler for file uploads and document processing."""

    def __init__(
        self,
        parser: DocumentParser | None = None,
        chunker: StructureAwareChunker | None = None,
        vector_store: DocumentVectorStore | None = None,
    ):
        """Initialize the upload handler.

        Args:
            parser: Document parser instance
            chunker: Text chunker instance
            vector_store: Vector store for document storage
        """
        self.parser = parser or SimpleDocumentParser()
        self.chunker = chunker or SimpleChunker()
        self.vector_store = vector_store

    def _detect_file_type(self, filename: str) -> str:
        """Detect file type from filename extension.

        Args:
            filename: Original filename

        Returns:
            File extension without dot (pdf, docx, txt, md, csv, json)
        """
        ext = Path(filename).suffix.lower().lstrip(".")

        # Map common extensions
        extension_map = {
            "pdf": "pdf",
            "docx": "docx",
            "doc": "docx",  # Will try docx parser
            "txt": "txt",
            "md": "md",
            "markdown": "md",
            "csv": "csv",
            "json": "json",
        }

        file_type = extension_map.get(ext, "txt")  # Default to txt for unknown
        return file_type

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text.

        Uses a simple heuristic: ~4 characters per token on average.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return len(text) // 4

    async def handle_upload(
        self,
        file_content: bytes,
        filename: str,
        metadata: dict | None = None,
    ) -> FileUploadResponse:
        """Handle file upload and processing.

        Args:
            file_content: Raw file bytes
            filename: Original filename
            metadata: Optional metadata to attach to document

        Returns:
            FileUploadResponse with processing results
        """
        document_id = str(uuid.uuid4())
        metadata = metadata or {}
        temp_path = None

        try:
            # 1. Detect file type
            file_type = self._detect_file_type(filename)
            logger.info(
                "file_upload_started",
                document_id=document_id,
                filename=filename,
                file_type=file_type,
            )

            # 2. Save to temp file
            suffix = f".{file_type}"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_content)
                temp_path = tmp.name

            # 3. Parse document
            text_content = await self.parser.parse(temp_path, file_type)
            if not text_content or not text_content.strip():
                raise ValueError("No text content extracted from file")

            # 4. Chunk document
            doc_metadata = {
                **metadata,
                "document_id": document_id,
                "filename": filename,
                "file_type": file_type,
                "upload_time": datetime.utcnow().isoformat(),
            }
            chunks = self.chunker.chunk(text_content, doc_metadata)

            # 5. Store in vector store if available
            if self.vector_store and chunks:
                # Prepare documents for storage
                documents = [
                    {
                        "content": chunk["content"],
                        "metadata": chunk["metadata"],
                    }
                    for chunk in chunks
                ]
                await self.vector_store.add_documents(documents)

            # 6. Calculate stats
            total_tokens = self._estimate_tokens(text_content)

            logger.info(
                "file_upload_completed",
                document_id=document_id,
                filename=filename,
                chunks_created=len(chunks),
                total_tokens=total_tokens,
            )

            return FileUploadResponse(
                document_id=document_id,
                filename=filename,
                file_type=file_type,
                chunks_created=len(chunks),
                total_tokens=total_tokens,
                status="success",
                message=f"Successfully processed {filename} ({len(chunks)} chunks)",
            )

        except Exception as e:
            logger.error(
                "file_upload_failed",
                document_id=document_id,
                filename=filename,
                error=str(e),
            )
            raise

        finally:
            # Clean up temp file
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    async def list_documents(self) -> list[dict]:
        """List all uploaded documents.

        Returns:
            List of document info dictionaries
        """
        if not self.vector_store:
            return []

        try:
            docs = await self.vector_store.get_all_documents()
            # Group by document_id to get unique documents
            documents_by_id: dict[str, dict] = {}

            for doc in docs:
                meta = doc.get("metadata", {})
                doc_id = meta.get("document_id")
                if not doc_id:
                    continue

                if doc_id not in documents_by_id:
                    documents_by_id[doc_id] = {
                        "id": doc_id,
                        "filename": meta.get("filename", "unknown"),
                        "file_type": meta.get("file_type", "unknown"),
                        "upload_time": meta.get("upload_time", datetime.utcnow().isoformat()),
                        "chunk_count": 0,
                        "total_tokens": 0,
                    }
                documents_by_id[doc_id]["chunk_count"] += 1

            return list(documents_by_id.values())
        except Exception as e:
            logger.error("list_documents_failed", error=str(e))
            return []

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document and all its chunks.

        Args:
            document_id: Document identifier to delete

        Returns:
            True if deleted successfully
        """
        if not self.vector_store:
            return False

        try:
            await self.vector_store.delete_by_metadata({"document_id": document_id})
            logger.info("document_deleted", document_id=document_id)
            return True
        except Exception as e:
            logger.error("delete_document_failed", document_id=document_id, error=str(e))
            return False
