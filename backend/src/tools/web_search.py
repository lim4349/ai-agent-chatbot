"""Web search tool using Tavily API."""

from tavily import AsyncTavilyClient

from src.core.logging import get_logger

logger = get_logger(__name__)


class WebSearchTool:
    """Web search tool using Tavily API."""

    name = "web_search"
    description = "Search the web for current information"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: AsyncTavilyClient | None = None

    async def _get_client(self) -> AsyncTavilyClient:
        """Get or create Tavily client."""
        if self._client is None:
            self._client = AsyncTavilyClient(api_key=self.api_key)
        return self._client

    async def execute(self, query: str, max_results: int = 5) -> str:
        """Execute web search and return formatted results.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            Formatted search results as string
        """
        logger.info("web_search_executing", query=query, max_results=max_results)

        try:
            client = await self._get_client()
            results = await client.search(query, max_results=max_results)

            formatted = []
            for r in results.get("results", []):
                title = r.get("title", "Untitled")
                url = r.get("url", "")
                content = r.get("content", "")[:500]  # Truncate long content
                # 마크다운 링크 형식으로 제공 (LLM이 인식하기 쉬움)
                formatted.append(f"### [{title}]({url})\n{content}\n")

            result_text = "\n---\n".join(formatted)
            logger.info(
                "web_search_completed",
                results_count=len(formatted),
                urls=[r.get("url") for r in results.get("results", [])],
            )
            # Debug: Log raw search results being sent to LLM
            logger.debug(
                "web_search_raw_results_for_llm",
                formatted_results=result_text[:1000] if len(result_text) > 1000 else result_text,
            )
            return result_text

        except Exception as e:
            logger.error("web_search_failed", error=str(e))
            raise
