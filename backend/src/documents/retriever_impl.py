"""Pinecone implementation of the DocumentRetriever protocol."""

from __future__ import annotations

from src.core.logging import get_logger
from src.core.protocols import DocumentRetriever
from src.documents.chunker import StructureAwareChunker
from src.documents.models import Document
from src.documents.parser import DocumentParser
from src.documents.pinecone_store import PineconeVectorStore

logger = get_logger(__name__)


class PineconeDocumentRetriever(DocumentRetriever):
    """Document retriever implementation using Pinecone vector store."""

    def __init__(
        self,
        vector_store: PineconeVectorStore,
        chunker: StructureAwareChunker,
        parser: DocumentParser,
    ):
        """Initialize the retriever.

        Args:
            vector_store: PineconeVectorStore instance for storage and search
            chunker: Chunker for document chunking (provided by container)
            parser: DocumentParser for parsing documents (provided by container)
        """
        self.vector_store = vector_store
        self.chunker = chunker
        self.parser = parser

    async def retrieve(
        self,
        query: str,
        top_k: int = 3,
        session_id: str | None = None,
    ) -> list[dict]:
        """Retrieve relevant document chunks.

        Args:
            query: Search query text
            top_k: Number of results to return
            session_id: Optional session ID for filtering documents

        Returns:
            List of document chunks with content, metadata, and score
            Format: [{"content": str, "metadata": dict, "score": float}]
        """
        logger.info("retrieving_documents", query=query[:50], top_k=top_k, session_id=session_id)

        # Build filters for session isolation
        filters = {}
        if session_id:
            filters["session_id"] = session_id

        results = await self.vector_store.search(
            query=query,
            top_k=top_k,
            filters=filters if filters else None,
        )

        # Format results for RAGAgent
        formatted_results = []
        for result in results:
            formatted_result = {
                "content": result.chunk_content,
                "metadata": {
                    "source": result.metadata.get("source", "unknown"),
                    "filename": result.metadata.get("filename", "unknown"),
                    "file_type": result.metadata.get("file_type", "unknown"),
                    "page": result.metadata.get("page"),
                    "heading": result.metadata.get("heading"),
                    "chunk_index": result.metadata.get("chunk_index", 0),
                    "total_chunks": result.metadata.get("total_chunks", 1),
                    "document_id": result.document_id,
                },
                "score": result.score,
            }
            formatted_results.append(formatted_result)

        logger.info("retrieval_completed", results_count=len(formatted_results))
        return formatted_results

    async def add_documents(self, documents: list[dict]) -> None:
        """Add documents to the retriever (parse, chunk, embed, store).

        Args:
            documents: List of document dictionaries with:
                - content: Raw document content or file path
                - filename: Original filename
                - file_type: Document type (txt, md, pdf, etc.)
                - metadata: Optional additional metadata
        """
        logger.info("adding_documents", count=len(documents))

        for doc_dict in documents:
            try:
                await self._process_and_store_document(doc_dict)
            except Exception as e:
                logger.error(
                    "failed_to_process_document",
                    error=str(e),
                    filename=doc_dict.get("filename", "unknown"),
                )
                # Continue processing other documents
                continue

        logger.info("documents_added", count=len(documents))

    async def _process_and_store_document(self, doc_dict: dict) -> None:
        """Process a single document and store it.

        Args:
            doc_dict: Document dictionary with content and metadata
        """
        from datetime import datetime

        content = doc_dict.get("content", "")
        filename = doc_dict.get("filename", "unnamed")
        file_type = doc_dict.get("file_type", "txt")
        metadata = doc_dict.get("metadata", {})

        # If content is a file path, parse it
        if not content and doc_dict.get("file_path"):
            parsed_doc = await self.parser.parse_file(doc_dict["file_path"])
            content = parsed_doc.content
            file_type = parsed_doc.file_type
            metadata.update(parsed_doc.metadata)

        if not content:
            logger.warning("empty_document_content", filename=filename)
            return

        # Generate document ID
        import hashlib
        import uuid

        doc_id = hashlib.sha256(f"{filename}_{uuid.uuid4().hex}".encode()).hexdigest()[:16]

        # Create Document object
        document = Document(
            id=doc_id,
            filename=filename,
            file_type=file_type,
            upload_time=datetime.utcnow(),
            chunks=[],
            total_tokens=0,
            metadata=metadata,
        )

        # Parse content into structured document if needed
        if file_type in ("md", "markdown", "html", "rst"):
            parsed = self.parser.parse_markdown(content)
            document.chunks = parsed.chunks
            document.total_tokens = parsed.total_tokens
        elif file_type == "json":
            parsed = self.parser.parse_json(content)
            document.chunks = parsed.chunks
            document.total_tokens = parsed.total_tokens
        else:
            # Plain text - use chunker directly
            chunks = self.chunker.chunk_text(content, source=filename)
            document.chunks = chunks
            document.total_tokens = sum(c.metadata.token_count for c in chunks)

        if not document.chunks:
            logger.warning("no_chunks_generated", filename=filename)
            return

        # Store in vector store
        await self.vector_store.add_document(document)

        logger.info(
            "document_processed_and_stored",
            document_id=doc_id,
            filename=filename,
            chunk_count=len(document.chunks),
        )

    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the retriever.

        Args:
            doc_id: Document ID to delete

        Returns:
            True if deleted successfully
        """
        return await self.vector_store.delete_document(doc_id)

    async def get_document_stats(self, doc_id: str) -> dict | None:
        """Get statistics for a document.

        Args:
            doc_id: Document ID

        Returns:
            Dictionary with document stats or None if not found
        """
        stats = await self.vector_store.get_document_stats(doc_id)
        if not stats:
            return None

        return {
            "document_id": stats.document_id,
            "chunk_count": stats.chunk_count,
            "total_tokens": stats.total_tokens,
            "filename": stats.filename,
            "file_type": stats.file_type,
            "upload_time": stats.upload_time.isoformat() if stats.upload_time else None,
        }
