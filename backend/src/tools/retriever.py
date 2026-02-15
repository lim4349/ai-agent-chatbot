"""Document retriever tool wrapper."""

from src.core.logging import get_logger

logger = get_logger(__name__)


class RetrieverTool:
    """Wrapper for document retriever as a tool."""

    name = "retriever"
    description = "Retrieve relevant documents from the knowledge base"

    def __init__(self, retriever):
        self.retriever = retriever

    async def execute(self, query: str, top_k: int = 3) -> list[dict]:
        """Retrieve relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of document chunks with content, metadata, and score
        """
        logger.info("retriever_executing", query=query, top_k=top_k)

        try:
            results = await self.retriever.retrieve(query, top_k=top_k)
            logger.info("retriever_completed", results_count=len(results))
            return results
        except Exception as e:
            logger.error("retriever_failed", error=str(e))
            raise
