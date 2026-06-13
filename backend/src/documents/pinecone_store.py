"""Pinecone document vector store for RAG."""

from __future__ import annotations

import asyncio
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
    parent_chunk_count: int = 0
    child_chunk_count: int = 0
    page_count: int = 0
    table_count: int = 0
    element_count: int = 0
    parse_warnings: list[str] | None = None


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
        device_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        """Add a document with all its chunks to the vector store.

        Args:
            document: Document object with chunks to store
            device_id: Device ID for document isolation (guest mode)
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

        # Use device-specific namespace for isolation (guest mode)
        namespace = f"device_{device_id}" if device_id else self.namespace

        # Prepare data for Pinecone
        vectors = []
        texts_to_embed = []
        embedding_vector_indices = []
        parse_summary = document.metadata.get("parse_summary", {})
        parent_chunk_count = sum(
            1 for chunk in document.chunks if getattr(chunk.metadata, "record_type", "") == "parent"
        )
        child_chunk_count = sum(
            1 for chunk in document.chunks if getattr(chunk.metadata, "record_type", "") == "child"
        )

        for chunk in document.chunks:
            chunk_id = f"{document.id}_{chunk.id}"
            record_type = getattr(chunk.metadata, "record_type", None) or "chunk"
            heading_path = list(getattr(chunk.metadata, "heading_path", []) or [])
            parse_warnings = parse_summary.get("warnings", [])

            # Build metadata with user/session isolation
            metadata = {
                "document_id": document.id,
                "chunk_id": chunk.id,
                "filename": document.filename,
                "file_type": document.file_type,
                "source": chunk.metadata.source,
                "page": chunk.metadata.page,
                "page_end": getattr(chunk.metadata, "page_end", None),
                "heading": chunk.metadata.heading,
                "heading_path": heading_path,
                "heading_path_text": " > ".join(heading_path),
                "section_type": chunk.metadata.section_type,
                "record_type": record_type,
                "parent_id": getattr(chunk.metadata, "parent_id", None),
                "child_id": getattr(chunk.metadata, "child_id", None),
                "chunk_index": chunk.metadata.chunk_index,
                "total_chunks": chunk.metadata.total_chunks,
                "char_count": chunk.metadata.char_count,
                "token_count": chunk.metadata.token_count,
                "parent_chunk_count": parent_chunk_count,
                "child_chunk_count": child_chunk_count,
                "parse_page_count": parse_summary.get("page_count", 0),
                "parse_table_count": parse_summary.get("table_count", 0),
                "parse_element_count": parse_summary.get("element_count", 0),
                "parse_warnings": parse_warnings[:10] if isinstance(parse_warnings, list) else [],
                "upload_time": document.upload_time.isoformat() if document.upload_time else None,
                # Pinecone requires string values for metadata filtering
                "text": chunk.content,  # Store text in metadata
            }
            # Add device/session isolation metadata
            if device_id:
                metadata["device_id"] = device_id
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
            if record_type != "parent":
                texts_to_embed.append(chunk.content)
                embedding_vector_indices.append(len(vectors) - 1)

        # Generate embeddings
        logger.info(
            "generating_embeddings",
            document_id=document.id,
            chunk_count=len(texts_to_embed),
        )
        embeddings = await self.embedding_generator.generate(texts_to_embed)

        # Add embeddings to vectors
        for vector_index, embedding in zip(embedding_vector_indices, embeddings, strict=True):
            vectors[vector_index]["values"] = embedding

        # Parent records are stored for context hydration, not vector recall.
        empty_vector = self._empty_query_vector()
        for vector in vectors:
            if "values" not in vector:
                vector["values"] = empty_vector

        # Upsert to Pinecone (batch in chunks of 100)
        batch_size = 100
        try:
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                await asyncio.to_thread(
                    self._index.upsert,
                    vectors=batch,
                    namespace=namespace,
                )

            logger.info(
                "document_added_to_store",
                document_id=document.id,
                chunk_count=len(vectors),
                device_id=device_id,
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
        device_id: str | None = None,
    ) -> list[SearchResult]:
        """Search for relevant document chunks.

        Args:
            query: Search query text
            top_k: Number of results to return
            filters: Optional metadata filters
            device_id: Device ID for namespace isolation (guest mode)

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

        # Use device-specific namespace for isolation (guest mode)
        namespace = f"device_{device_id}" if device_id else self.namespace

        # Query Pinecone
        try:
            results = await asyncio.to_thread(
                self._index.query,
                vector=query_embedding,
                top_k=top_k,
                namespace=namespace,
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

    async def get_chunk(
        self,
        *,
        document_id: str,
        chunk_id: str,
        device_id: str | None = None,
    ) -> SearchResult | None:
        """Fetch one stored chunk by document/chunk ID for parent context hydration."""
        if not self._index:
            logger.error("pinecone_not_initialized")
            return None

        namespace = f"device_{device_id}" if device_id else self.namespace
        vector_id = f"{document_id}_{chunk_id}"

        try:
            response = await asyncio.to_thread(
                self._index.fetch,
                ids=[vector_id],
                namespace=namespace,
            )
        except Exception as e:
            logger.error("chunk_fetch_failed", error=str(e), document_id=document_id)
            return None

        vectors = getattr(response, "vectors", None)
        if vectors is None and isinstance(response, dict):
            vectors = response.get("vectors")
        if not vectors:
            return None

        record = vectors.get(vector_id)
        if not record:
            return None

        metadata = getattr(record, "metadata", None)
        if metadata is None and isinstance(record, dict):
            metadata = record.get("metadata")
        metadata = dict(metadata or {})

        return SearchResult(
            chunk_content=metadata.get("text", ""),
            score=0.0,
            document_id=metadata.get("document_id", document_id),
            metadata=metadata,
        )

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

    async def delete_document(self, doc_id: str, device_id: str | None = None) -> None:
        """Delete all chunks for a document.

        Args:
            doc_id: Document ID to delete
            device_id: Device ID for ownership verification (guest mode)

        Raises:
            RuntimeError: If Pinecone is not initialized
            Exception: If deletion fails
        """
        if not self._index:
            raise RuntimeError("Pinecone not initialized")

        # Use device-specific namespace
        namespace = f"device_{device_id}" if device_id else self.namespace

        # Delete by filter
        await asyncio.to_thread(
            self._index.delete,
            filter={"document_id": {"$eq": doc_id}},
            namespace=namespace,
        )

        logger.info("document_deleted", document_id=doc_id, device_id=device_id)

    async def has_documents_for_session(self, device_id: str, session_id: str) -> bool:
        """Check if any documents exist for a session.

        Args:
            device_id: Device ID (guest mode)
            session_id: Session ID

        Returns:
            True if documents exist for this session
        """
        if not self._index:
            return False

        namespace = f"device_{device_id}"
        try:
            results = await asyncio.to_thread(
                self._index.query,
                vector=self._empty_query_vector(),
                top_k=1,
                filter={"session_id": {"$eq": session_id}},
                namespace=namespace,
                include_metadata=False,
            )
            return len(results.matches) > 0
        except Exception:
            return False

    async def delete_session_documents(self, device_id: str, session_id: str) -> int:
        """Delete all documents for a session.

        Args:
            device_id: Device ID (guest mode)
            session_id: Session ID

        Returns:
            Number of documents deleted
        """
        if not self._index:
            logger.error("pinecone_not_initialized")
            return 0

        # Use device-specific namespace
        namespace = f"device_{device_id}"

        try:
            # First, query to get document count
            results = await asyncio.to_thread(
                self._index.query,
                vector=self._empty_query_vector(),
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
            await asyncio.to_thread(
                self._index.delete,
                filter={"session_id": {"$eq": session_id}},
                namespace=namespace,
            )

            logger.info(
                "session_documents_deleted",
                session_id=session_id,
                device_id=device_id,
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
        self,
        doc_id: str,
        device_id: str | None = None,
        session_id: str | None = None,
    ) -> DocumentStats | None:
        """Get statistics for a document.

        Args:
            doc_id: Document ID
            device_id: Device ID for ownership verification (guest mode)
            session_id: Optional session ID for document isolation

        Returns:
            DocumentStats object or None if not found
        """
        if not self._index:
            logger.error("pinecone_not_initialized")
            return None

        # Use device-specific namespace
        namespace = f"device_{device_id}" if device_id else self.namespace

        try:
            # Query with filter to get all chunks
            # Use dummy vector to query
            filters = {"document_id": {"$eq": doc_id}}
            if session_id:
                filters["session_id"] = {"$eq": session_id}

            results = await asyncio.to_thread(
                self._index.query,
                vector=self._empty_query_vector(),
                top_k=1000,
                namespace=namespace,
                filter=filters,
                include_metadata=True,
            )

            if not results.matches:
                return None

            metadatas = [match.metadata for match in results.matches if match.metadata]
            if not metadatas:
                return None

            # Aggregate stats. Parent chunks represent LLM context; child chunks represent search
            # records. Older documents without record_type are counted as child/search chunks.
            parent_metadatas = [
                m for m in metadatas if isinstance(m, dict) and m.get("record_type") == "parent"
            ]
            child_metadatas = [
                m
                for m in metadatas
                if isinstance(m, dict) and m.get("record_type", "child") != "parent"
            ]
            chunk_count = len(results.matches)
            token_metadatas = parent_metadatas or metadatas
            total_tokens = sum(
                m.get("token_count", 0) for m in token_metadatas if isinstance(m, dict)
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

            parse_warnings = first_meta.get("parse_warnings", [])
            if not isinstance(parse_warnings, list):
                parse_warnings = []

            return DocumentStats(
                document_id=doc_id,
                chunk_count=chunk_count,
                total_tokens=total_tokens,
                filename=filename,
                file_type=file_type,
                upload_time=upload_time,
                parent_chunk_count=len(parent_metadatas),
                child_chunk_count=len(child_metadatas),
                page_count=int(first_meta.get("parse_page_count") or 0),
                table_count=int(first_meta.get("parse_table_count") or 0),
                element_count=int(first_meta.get("parse_element_count") or 0),
                parse_warnings=[str(warning) for warning in parse_warnings],
            )
        except Exception as e:
            logger.error("failed_to_get_document_stats", error=str(e), document_id=doc_id)
            return None

    async def list_documents(
        self,
        device_id: str | None = None,
        session_id: str | None = None,
    ) -> list[str]:
        """List all unique document IDs in the store.

        Args:
            device_id: Device ID for filtering (guest mode)
            session_id: Optional session ID for document isolation

        Returns:
            List of document IDs
        """
        if not self._index:
            logger.error("pinecone_not_initialized")
            return []

        # Use device-specific namespace
        namespace = f"device_{device_id}" if device_id else self.namespace

        try:
            # List all vectors with metadata
            # Note: Pinecone doesn't have a direct list_all, we need to query
            filters = {"session_id": {"$eq": session_id}} if session_id else None

            results = await asyncio.to_thread(
                self._index.query,
                vector=self._empty_query_vector(),
                top_k=1000,
                namespace=namespace,
                filter=filters,
                include_metadata=True,
            )

            doc_ids = set()
            for match in results.matches:
                if match.metadata and "document_id" in match.metadata:
                    doc_ids.add(match.metadata["document_id"])

            return sorted(doc_ids)
        except Exception as e:
            logger.error(
                "failed_to_list_documents",
                error=str(e),
                device_id=device_id,
                session_id=session_id,
            )
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
            await asyncio.to_thread(
                self._index.delete,
                delete_all=True,
                namespace=self.namespace,
            )
            logger.info("store_cleared", index=self.index_name, namespace=self.namespace)
            return True
        except Exception as e:
            logger.error("failed_to_clear_store", error=str(e))
            return False

    def _empty_query_vector(self) -> list[float]:
        """Return a metadata-query vector matching the configured embedding dimension."""
        dimension = getattr(self.embedding_generator, "dimension", None)
        if isinstance(dimension, int) and dimension > 0:
            return [0.0] * dimension
        return [0.0] * 1024
