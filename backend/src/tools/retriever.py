"""Document retriever tool wrapper."""

from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


class RetrieverTool:
    """Wrapper for document retriever as a tool."""

    name = "retriever"
    description = "Retrieve relevant documents from the knowledge base"

    def __init__(self, retriever: Any) -> None:
        self.retriever = retriever

    async def execute(
        self,
        query: str,
        top_k: int = 3,
        session_id: str | None = None,
        device_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return
            session_id: Optional session ID for filtering documents
            device_id: Optional device ID for namespace isolation

        Returns:
            List of document chunks with content, metadata, and score
        """
        logger.info("retriever_executing", query=query, top_k=top_k)

        try:
            results = await self.retriever.retrieve(
                query,
                top_k=top_k,
                session_id=session_id,
                device_id=device_id,
            )
            logger.info("retriever_completed", results_count=len(results))
            return results
        except Exception as e:
            logger.error("retriever_failed", error=str(e))
            raise
