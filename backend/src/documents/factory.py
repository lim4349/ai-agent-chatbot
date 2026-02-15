"""Factory for creating document processing components."""

from src.core.config import AppConfig
from src.core.protocols import DocumentChunker, DocumentParser


class DocumentProcessorFactory:
    """Factory for creating document processing components."""

    @staticmethod
    def create_parser() -> DocumentParser:
        """Create a document parser instance.

        Returns:
            DocumentParser implementation
        """
        from src.documents.parser import DocumentParser
        return DocumentParser()

    @staticmethod
    def create_chunker(config: AppConfig) -> DocumentChunker:
        """Create a document chunker instance.

        Args:
            config: Application configuration

        Returns:
            DocumentChunker implementation configured with RAG settings
        """
        from src.documents.chunking.domain_aware_chunker import DomainAwareChunker

        return DomainAwareChunker(
            max_tokens=config.rag.chunk_size,
            overlap_tokens=config.rag.chunk_overlap,
            strategy=config.rag.chunking_strategy,
        )
