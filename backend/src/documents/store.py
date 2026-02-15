"""ChromaDB document vector store for RAG."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from src.core.logging import get_logger
from src.documents.embeddings import EmbeddingGenerator
from src.documents.models import Document

if TYPE_CHECKING:
    import chromadb

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Result from a vector search."""

    chunk_content: str
    score: float
    document_id: str
    metadata: dict[str, Any]


@dataclass
class DocumentStats:
    """Statistics for a stored document."""

    document_id: str
    chunk_count: int
    total_tokens: int
    filename: str | None
    file_type: str | None
    upload_time: datetime | None


class DocumentVectorStore:
    """Vector store for documents using ChromaDB."""

    def __init__(
        self,
        collection_name: str = "documents",
        persist_directory: str | None = None,
        embedding_generator: EmbeddingGenerator | None = None,
        chroma_host: str | None = None,
        chroma_port: int = 8000,
        chroma_token: str | None = None,
    ):
        """Initialize the document vector store.

        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory to persist ChromaDB data (for embedded mode)
            embedding_generator: Optional embedding generator instance
            chroma_host: ChromaDB server host (for HTTP client mode)
            chroma_port: ChromaDB server port (for HTTP client mode)
            chroma_token: ChromaDB authentication token
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.chroma_host = chroma_host
        self.chroma_port = chroma_port
        self.chroma_token = chroma_token
        self.embedding_generator = embedding_generator or EmbeddingGenerator()

        # Initialize ChromaDB
        self._client: chromadb.Client | None = None
        self._collection: chromadb.Collection | None = None
        self._init_chroma()

    def _init_chroma(self) -> None:
        """Initialize ChromaDB client and collection."""
        try:
            import chromadb
            from chromadb.config import Settings

            # HTTP client mode (for external ChromaDB server)
            if self.chroma_host:
                settings = Settings(
                    anonymized_telemetry=False,
                    chroma_client_auth_provider="chromadb.auth.token.TokenAuthClientProvider",
                    chroma_client_auth_credentials=self.chroma_token or "",
                )
                self._client = chromadb.HttpClient(
                    host=self.chroma_host,
                    port=self.chroma_port,
                    settings=settings,
                )
                logger.info(
                    "chromadb_http_client_initialized",
                    host=self.chroma_host,
                    port=self.chroma_port,
                )
            # Persistent client mode (for embedded ChromaDB with disk persistence)
            elif self.persist_directory:
                self._client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=Settings(anonymized_telemetry=False),
                )
                logger.info(
                    "chromadb_persistent_client_initialized",
                    path=self.persist_directory,
                )
            # Ephemeral client mode (in-memory only)
            else:
                self._client = chromadb.Client(
                    settings=Settings(anonymized_telemetry=False)
                )
                logger.info("chromadb_ephemeral_client_initialized")

            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
            )
            logger.info(
                "chromadb_collection_ready",
                collection=self.collection_name,
            )
        except ImportError:
            logger.error("chromadb_not_installed")
            raise
        except Exception as e:
            logger.error("chromadb_init_failed", error=str(e))
            raise

    async def add_document(self, document: Document) -> str:
        """Add a document with all its chunks to the vector store.

        Args:
            document: Document object with chunks to store

        Returns:
            Document ID
        """
        if not isinstance(document, Document):
            raise TypeError(f"Expected Document, got {type(document)}")

        if not document.chunks:
            logger.warning("document_has_no_chunks", document_id=document.id)
            return document.id

        # Prepare data for ChromaDB
        ids: list[str] = []
        texts: list[str] = []
        metadatas: list[dict] = []

        for chunk in document.chunks:
            chunk_id = f"{document.id}_{chunk.id}"
            ids.append(chunk_id)
            texts.append(chunk.content)

            # Build metadata
            metadata = {
                "document_id": document.id,
                "chunk_id": chunk.id,
                "filename": document.filename,
                "file_type": document.file_type,
                "source": chunk.metadata.source,
                "page": chunk.metadata.page,
                "heading": chunk.metadata.heading,
                "section_type": chunk.metadata.section_type,
                "chunk_index": chunk.metadata.chunk_index,
                "total_chunks": chunk.metadata.total_chunks,
                "char_count": chunk.metadata.char_count,
                "token_count": chunk.metadata.token_count,
                "upload_time": document.upload_time.isoformat(),
            }
            # Remove None values
            metadata = {k: v for k, v in metadata.items() if v is not None}
            metadatas.append(metadata)

        # Generate embeddings
        logger.info(
            "generating_embeddings",
            document_id=document.id,
            chunk_count=len(texts),
        )
        embeddings = await self.embedding_generator.generate(texts)

        # Add to ChromaDB
        try:
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            logger.info(
                "document_added_to_store",
                document_id=document.id,
                chunk_count=len(texts),
            )
        except Exception as e:
            logger.error("failed_to_add_document", error=str(e), document_id=document.id)
            raise

        return document.id

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """Search for relevant document chunks.

        Args:
            query: Search query text
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of search results with scores
        """
        if not query.strip():
            return []

        # Generate query embedding
        query_embedding = await self.embedding_generator.embed_query(query)

        if not query_embedding:
            logger.warning("empty_query_embedding")
            return []

        # Build where clause from filters
        where_clause = self._build_where_clause(filters)

        # Query ChromaDB
        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause if where_clause else None,
            )
        except Exception as e:
            logger.error("search_failed", error=str(e))
            return []

        # Format results
        search_results: list[SearchResult] = []

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, metadata, distance in zip(
            documents, metadatas, distances, strict=False
        ):
            # Convert distance to similarity score (ChromaDB returns distances)
            # Cosine distance to similarity: score = 1 - distance
            score = 1.0 - float(distance) if distance is not None else 0.0

            result = SearchResult(
                chunk_content=doc,
                score=max(0.0, min(1.0, score)),  # Clamp to [0, 1]
                document_id=metadata.get("document_id", "unknown"),
                metadata=dict(metadata),
            )
            search_results.append(result)

        logger.info(
            "search_completed",
            query=query[:50],
            results_count=len(search_results),
        )

        return search_results

    def _build_where_clause(self, filters: dict | None) -> dict | None:
        """Build ChromaDB where clause from filters.

        Args:
            filters: Dictionary of metadata filters

        Returns:
            ChromaDB where clause dictionary
        """
        if not filters:
            return None

        # Simple equality filters
        where_parts = {}
        for key, value in filters.items():
            if value is not None:
                where_parts[key] = value

        return where_parts if where_parts else None

    async def delete_document(self, doc_id: str) -> bool:
        """Delete all chunks for a document.

        Args:
            doc_id: Document ID to delete

        Returns:
            True if deleted successfully
        """
        try:
            # Find all chunks for this document
            results = self._collection.get(
                where={"document_id": doc_id},
            )

            if not results or not results["ids"]:
                logger.warning("document_not_found_for_deletion", document_id=doc_id)
                return False

            # Delete all chunks
            self._collection.delete(
                ids=results["ids"],
            )

            logger.info(
                "document_deleted",
                document_id=doc_id,
                chunks_deleted=len(results["ids"]),
            )
            return True
        except Exception as e:
            logger.error("failed_to_delete_document", error=str(e), document_id=doc_id)
            return False

    async def get_document_stats(self, doc_id: str) -> DocumentStats | None:
        """Get statistics for a document.

        Args:
            doc_id: Document ID

        Returns:
            DocumentStats object or None if not found
        """
        try:
            results = self._collection.get(
                where={"document_id": doc_id},
            )

            if not results or not results["ids"]:
                return None

            metadatas = results.get("metadatas", [])
            if not metadatas:
                return None

            # Aggregate stats
            chunk_count = len(results["ids"])
            total_tokens = sum(
                m.get("token_count", 0) for m in metadatas if isinstance(m, dict)
            )

            # Get common metadata from first chunk
            first_meta = metadatas[0] if metadatas else {}
            filename = first_meta.get("filename") if isinstance(first_meta, dict) else None
            file_type = first_meta.get("file_type") if isinstance(first_meta, dict) else None
            upload_time_str = (
                first_meta.get("upload_time") if isinstance(first_meta, dict) else None
            )

            upload_time = None
            if upload_time_str:
                with contextlib.suppress(ValueError):
                    upload_time = datetime.fromisoformat(upload_time_str)

            return DocumentStats(
                document_id=doc_id,
                chunk_count=chunk_count,
                total_tokens=total_tokens,
                filename=filename,
                file_type=file_type,
                upload_time=upload_time,
            )
        except Exception as e:
            logger.error("failed_to_get_document_stats", error=str(e), document_id=doc_id)
            return None

    async def list_documents(self) -> list[str]:
        """List all unique document IDs in the store.

        Returns:
            List of document IDs
        """
        try:
            results = self._collection.get()

            if not results or not results.get("metadatas"):
                return []

            doc_ids = set()
            for metadata in results["metadatas"]:
                if isinstance(metadata, dict) and "document_id" in metadata:
                    doc_ids.add(metadata["document_id"])

            return sorted(doc_ids)
        except Exception as e:
            logger.error("failed_to_list_documents", error=str(e))
            return []

    async def clear(self) -> bool:
        """Clear all documents from the store.

        Returns:
            True if cleared successfully
        """
        try:
            # Delete and recreate collection
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
            )
            logger.info("store_cleared", collection=self.collection_name)
            return True
        except Exception as e:
            logger.error("failed_to_clear_store", error=str(e))
            return False
