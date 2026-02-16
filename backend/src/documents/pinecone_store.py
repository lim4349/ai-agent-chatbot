"""Pinecone document vector store for RAG."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.core.logging import get_logger
from src.documents.embeddings import EmbeddingGenerator
from src.documents.models import Document

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


class PineconeVectorStore:
    """Vector store for documents using Pinecone."""

    def __init__(
        self,
        api_key: str | None = None,
        index_name: str = "documents",
        embedding_generator: EmbeddingGenerator | None = None,
        namespace: str = "default",
    ):
        """Initialize the Pinecone vector store.

        Args:
            api_key: Pinecone API key
            index_name: Name of the Pinecone index
            embedding_generator: Optional embedding generator instance
            namespace: Namespace for data isolation
        """
        self.index_name = index_name
        self.namespace = namespace
        self.embedding_generator = embedding_generator or EmbeddingGenerator()
        self._api_key = api_key

        # Initialize Pinecone
        self._index = None
        self._init_pinecone()

    def _init_pinecone(self) -> None:
        """Initialize Pinecone client and index."""
        try:
            from pinecone import Pinecone

            if not self._api_key:
                logger.warning("pinecone_api_key_not_set")
                return

            # Initialize Pinecone client
            pc = Pinecone(api_key=self._api_key)

            # Check if index exists
            if self.index_name not in pc.list_indexes().names():
                logger.warning(
                    "pinecone_index_not_found",
                    index=self.index_name,
                )
                return

            # Get index
            self._index = pc.Index(self.index_name)
            logger.info(
                "pinecone_initialized",
                index=self.index_name,
                namespace=self.namespace,
            )

        except ImportError:
            logger.error("pinecone_not_installed")
            raise
        except Exception as e:
            logger.error("pinecone_init_failed", error=str(e))
            raise

    async def add_document(
        self,
        document: Document,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        """Add a document with all its chunks to the vector store.

        Args:
            document: Document object with chunks to store
            user_id: User ID for document isolation
            session_id: Session ID for document isolation

        Returns:
            Document ID
        """
        if not isinstance(document, Document):
            raise TypeError(f"Expected Document, got {type(document)}")

        if not document.chunks:
            logger.warning("document_has_no_chunks", document_id=document.id)
            return document.id

        if not self._index:
            logger.error("pinecone_not_initialized")
            raise RuntimeError("Pinecone not initialized")

        # Use user-specific namespace for isolation
        namespace = f"user_{user_id}" if user_id else self.namespace

        # Prepare data for Pinecone
        vectors = []

        for chunk in document.chunks:
            chunk_id = f"{document.id}_{chunk.id}"

            # Build metadata with user/session isolation
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
                "upload_time": document.upload_time.isoformat() if document.upload_time else None,
                # Pinecone requires string values for metadata filtering
                "text": chunk.content,  # Store text in metadata
            }
            # Add user/session isolation metadata
            if user_id:
                metadata["user_id"] = user_id
            if session_id:
                metadata["session_id"] = session_id

            # Remove None values
            metadata = {k: v for k, v in metadata.items() if v is not None}

            vectors.append(
                {
                    "id": chunk_id,
                    "metadata": metadata,
                }
            )

        # Generate embeddings
        logger.info(
            "generating_embeddings",
            document_id=document.id,
            chunk_count=len(vectors),
        )
        texts = [chunk.content for chunk in document.chunks]
        embeddings = await self.embedding_generator.generate(texts)

        # Add embeddings to vectors
        for i, embedding in enumerate(embeddings):
            vectors[i]["values"] = embedding

        # Upsert to Pinecone (batch in chunks of 100)
        batch_size = 100
        try:
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                self._index.upsert(
                    vectors=batch,
                    namespace=namespace,
                )

            logger.info(
                "document_added_to_store",
                document_id=document.id,
                chunk_count=len(vectors),
                user_id=user_id,
                session_id=session_id,
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
        if not self._index:
            logger.error("pinecone_not_initialized")
            return []

        if not query.strip():
            return []

        # Generate query embedding
        query_embedding = await self.embedding_generator.embed_query(query)

        if not query_embedding:
            logger.warning("empty_query_embedding")
            return []

        # Build filter
        pinecone_filter = self._build_filter(filters)

        # Query Pinecone
        try:
            results = self._index.query(
                vector=query_embedding,
                top_k=top_k,
                namespace=self.namespace,
                filter=pinecone_filter,
                include_metadata=True,
            )
        except Exception as e:
            logger.error("search_failed", error=str(e))
            return []

        # Format results
        search_results: list[SearchResult] = []

        for match in results.matches:
            metadata = match.metadata or {}

            result = SearchResult(
                chunk_content=metadata.get("text", ""),
                score=match.score if match.score else 0.0,
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

    def _build_filter(self, filters: dict | None) -> dict | None:
        """Build Pinecone filter from filters.

        Args:
            filters: Dictionary of metadata filters

        Returns:
            Pinecone filter dictionary
        """
        if not filters:
            return None

        # Build filter
        pinecone_filter = {}
        for key, value in filters.items():
            if value is not None:
                pinecone_filter[key] = {"$eq": value}

        return pinecone_filter if pinecone_filter else None

    async def delete_document(self, doc_id: str, user_id: str | None = None) -> None:
        """Delete all chunks for a document.

        Args:
            doc_id: Document ID to delete
            user_id: User ID for ownership verification

        Raises:
            RuntimeError: If Pinecone is not initialized
            Exception: If deletion fails
        """
        if not self._index:
            raise RuntimeError("Pinecone not initialized")

        # Use user-specific namespace
        namespace = f"user_{user_id}" if user_id else self.namespace

        # Delete by filter
        self._index.delete(
            filter={"document_id": {"$eq": doc_id}},
            namespace=namespace,
        )

        logger.info("document_deleted", document_id=doc_id, user_id=user_id)

    async def delete_session_documents(self, user_id: str, session_id: str) -> int:
        """Delete all documents for a session.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            Number of documents deleted
        """
        if not self._index:
            logger.error("pinecone_not_initialized")
            return 0

        # Use user-specific namespace
        namespace = f"user_{user_id}"

        try:
            # First, query to get document count
            results = self._index.query(
                vector=[0.0] * 1024,
                top_k=1000,
                namespace=namespace,
                filter={"session_id": {"$eq": session_id}},
                include_metadata=True,
            )

            doc_ids = set()
            for match in results.matches:
                if match.metadata and "document_id" in match.metadata:
                    doc_ids.add(match.metadata["document_id"])

            # Delete by session_id filter
            self._index.delete(
                filter={"session_id": {"$eq": session_id}},
                namespace=namespace,
            )

            logger.info(
                "session_documents_deleted",
                session_id=session_id,
                user_id=user_id,
                document_count=len(doc_ids),
            )
            return len(doc_ids)
        except Exception as e:
            logger.error(
                "failed_to_delete_session_documents",
                error=str(e),
                session_id=session_id,
            )
            return 0

    async def get_document_stats(
        self, doc_id: str, user_id: str | None = None
    ) -> DocumentStats | None:
        """Get statistics for a document.

        Args:
            doc_id: Document ID
            user_id: User ID for ownership verification

        Returns:
            DocumentStats object or None if not found
        """
        if not self._index:
            logger.error("pinecone_not_initialized")
            return None

        # Use user-specific namespace
        namespace = f"user_{user_id}" if user_id else self.namespace

        try:
            # Query with filter to get all chunks
            # Use dummy vector to query
            results = self._index.query(
                vector=[0.0] * 1024,  # Dummy vector
                top_k=1000,
                namespace=namespace,
                filter={"document_id": {"$eq": doc_id}},
                include_metadata=True,
            )

            if not results.matches:
                return None

            metadatas = [match.metadata for match in results.matches if match.metadata]
            if not metadatas:
                return None

            # Aggregate stats
            chunk_count = len(results.matches)
            total_tokens = sum(m.get("token_count", 0) for m in metadatas if isinstance(m, dict))

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

    async def list_documents(self, user_id: str | None = None) -> list[str]:
        """List all unique document IDs in the store.

        Args:
            user_id: User ID for filtering

        Returns:
            List of document IDs
        """
        if not self._index:
            logger.error("pinecone_not_initialized")
            return []

        # Use user-specific namespace
        namespace = f"user_{user_id}" if user_id else self.namespace

        try:
            # List all vectors with metadata
            # Note: Pinecone doesn't have a direct list_all, we need to query
            results = self._index.query(
                vector=[0.0] * 1024,
                top_k=1000,
                namespace=namespace,
                include_metadata=True,
            )

            doc_ids = set()
            for match in results.matches:
                if match.metadata and "document_id" in match.metadata:
                    doc_ids.add(match.metadata["document_id"])

            return sorted(doc_ids)
        except Exception as e:
            logger.error("failed_to_list_documents", error=str(e), user_id=user_id)
            return []

    async def clear(self) -> bool:
        """Clear all documents from the store.

        Returns:
            True if cleared successfully
        """
        if not self._index:
            logger.error("pinecone_not_initialized")
            return False

        try:
            # Delete all in namespace
            self._index.delete(
                delete_all=True,
                namespace=self.namespace,
            )
            logger.info("store_cleared", index=self.index_name, namespace=self.namespace)
            return True
        except Exception as e:
            logger.error("failed_to_clear_store", error=str(e))
            return False
