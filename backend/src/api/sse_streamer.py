"""SSE streaming event tracker for LangGraph graph execution."""

import json
from collections.abc import AsyncIterator

from src.core.logging import get_logger

logger = get_logger(__name__)

# Nodes that use non-streaming LLM calls.
NON_STREAMING_NODES = frozenset({"research"})

# All graph nodes that produce traceable events
GRAPH_TRACE_NODES = frozenset({
    "chat",
    "research",
})

# Status messages per node
NODE_STATUS_MESSAGES: dict[str, str] = {
    "research": "리서치 중...",
}

# Status messages per tool
TOOL_STATUS_MESSAGES: dict[str, str] = {
    "web_search": "웹 검색 중...",
    "retriever": "문서 검색 중...",
}


class SSEStreamer:
    """Tracks graph execution state and yields SSE events."""

    def __init__(self) -> None:
        self.streamed_nodes: set[str] = set()
        self.sent_content_hashes: set[int] = set()
        self.all_agents: list[str] = []

    def _add_agent(self, agent: str) -> bool:
        """Add agent to tracking list. Returns True if newly added."""
        if agent and agent not in self.all_agents:
            self.all_agents.append(agent)
            return True
        return False

    def _extract_content(self, chunk) -> str:
        """Extract text from a streaming chunk."""
        if not chunk or not hasattr(chunk, "content"):
            return ""
        content = chunk.content
        if isinstance(content, list):
            return "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        return content

    def _extract_last_message(self, output: dict) -> str:
        """Extract content from the last message in a node output."""
        messages = output.get("messages", [])
        if not messages:
            return ""
        last_msg = messages[-1]
        if isinstance(last_msg, dict):
            return last_msg.get("content", "")
        return getattr(last_msg, "content", "")

    def handle_chain_start(self, node_name: str) -> list[dict]:
        """Handle on_chain_start event."""
        events: list[dict] = []

        if node_name in GRAPH_TRACE_NODES and self._add_agent(node_name):
            events.append({
                "event": "agent",
                "data": json.dumps({"agent": node_name, "all_agents": self.all_agents}),
            })

        if node_name in NODE_STATUS_MESSAGES:
            events.append({
                "event": "status",
                "data": json.dumps({"message": NODE_STATUS_MESSAGES[node_name]}),
            })

        return events

    def handle_chat_model_stream(self, metadata: dict, chunk) -> list[dict]:
        """Handle on_chat_model_stream event."""
        langgraph_node = metadata.get("langgraph_node", "")

        # Skip routing and non-streaming nodes
        if langgraph_node == "router" or langgraph_node in NON_STREAMING_NODES:
            return []

        text = self._extract_content(chunk)
        if not text:
            return []

        self.streamed_nodes.add(langgraph_node)
        return [{"event": "token", "data": text}]

    def handle_tool_start(self, tool_name: str) -> list[dict]:
        """Handle on_tool_start event."""
        if tool_name in TOOL_STATUS_MESSAGES:
            return [{
                "event": "status",
                "data": json.dumps({"message": TOOL_STATUS_MESSAGES[tool_name]}),
            }]
        return []

    def handle_chain_end(self, node_name: str, output: dict) -> list[dict]:
        """Handle on_chain_end event."""
        events: list[dict] = []

        if node_name == "router":
            agent = output.get("next_agent", "chat")
            if self._add_agent(agent):
                events.append({
                    "event": "agent",
                    "data": json.dumps({"agent": agent, "all_agents": self.all_agents}),
                })

        elif node_name in NON_STREAMING_NODES:
            for tool_result in output.get("tool_results", []):
                events.append({
                    "event": "tool",
                    "data": json.dumps(tool_result, default=str),
                })

            content = self._extract_last_message(output)
            if content:
                content_hash = hash(content[:100])
                logger.info(
                    "sse_content_hash",
                    node_name=node_name,
                    content_hash=content_hash,
                    already_sent=content_hash in self.sent_content_hashes,
                )
                if content_hash not in self.sent_content_hashes:
                    self.sent_content_hashes.add(content_hash)
                    events.append({"event": "token", "data": content})

        elif node_name == "chat" and node_name not in self.streamed_nodes:
            content = self._extract_last_message(output)
            if content:
                content_hash = hash(content[:100])
                if content_hash not in self.sent_content_hashes:
                    self.sent_content_hashes.add(content_hash)
                    events.append({"event": "token", "data": content})

        return events

    def finalize(self) -> list[dict]:
        """Generate final events after streaming completes."""
        events: list[dict] = []
        if self.all_agents:
            events.append({
                "event": "agents_complete",
                "data": json.dumps({"agents": self.all_agents}),
            })
        events.append({"event": "done", "data": ""})
        return events


async def stream_graph_events(
    graph,
    initial_state: dict,
    graph_config: dict,
) -> AsyncIterator[dict]:
    """Stream LangGraph execution events as SSE-compatible dicts.

    Yields dicts with 'event' and 'data' keys suitable for EventSourceResponse.
    """
    streamer = SSEStreamer()

    try:
        async for event in graph.astream_events(
            initial_state, config=graph_config, version="v2"
        ):
            kind = event.get("event")

            if kind in ("on_chain_error", "on_tool_error"):
                error_data = event.get("data", {})
                logger.warning("stream_error", error=str(error_data))

            if kind == "on_chain_start":
                node_name = event.get("name", "")
                for ev in streamer.handle_chain_start(node_name):
                    yield ev

            elif kind == "on_chat_model_stream":
                metadata = event.get("metadata", {})
                chunk = event.get("data", {}).get("chunk")
                for ev in streamer.handle_chat_model_stream(metadata, chunk):
                    yield ev

            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                for ev in streamer.handle_tool_start(tool_name):
                    yield ev

            elif kind == "on_chain_end":
                node_name = event.get("name", "")
                output = event.get("data", {}).get("output", {})
                for ev in streamer.handle_chain_end(node_name, output):
                    yield ev

        for ev in streamer.finalize():
            yield ev

    except Exception as e:
        yield {"event": "error", "data": json.dumps({"error": str(e)})}
