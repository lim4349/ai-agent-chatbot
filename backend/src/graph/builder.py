"""LangGraph graph builder."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.core.logging import get_logger
from src.graph.edges import route_to_next_task
from src.graph.state import AgentState

logger = get_logger(__name__)


def build_graph(container):
    """Build and compile the multi-agent graph.

    Graph flow:
    START → router → deterministic tool nodes → specialist agent → END

    Args:
        container: DI container with all dependencies

    Returns:
        Compiled LangGraph
    """
    from src.agents.factory import AgentFactory
    from src.graph.router import heuristic_route
    from src.graph.tool_nodes import RetrieverCollectNode, WebSearchCollectNode
    from src.tools.retriever import RetrieverTool

    # Resolve providers to actual instances
    llm = container.llm()
    memory = container.memory()
    retriever = container.retriever()
    tool_registry = container.tool_registry()
    long_term_memory = container.long_term_memory()
    user_profiler = container.user_profiler()
    topic_memory = container.topic_memory()
    summarizer = container.summarizer()

    # Tool instances for chat agent
    search_tool = tool_registry.get("web_search") if tool_registry else None
    retriever_tool = RetrieverTool(retriever) if retriever else None

    # Create agent instances using factory with resolved dependencies
    chat = AgentFactory.create_chat(
        llm=llm,
        memory=memory,
        long_term_memory=long_term_memory,
        user_profiler=user_profiler,
        topic_memory=topic_memory,
        summarizer=summarizer,
        search_tool=search_tool,
        retriever=retriever_tool,
    )
    code = AgentFactory.create_code(
        llm=llm,
        memory=memory,
        tool_registry=tool_registry,
    )
    report = AgentFactory.create_report(
        llm=llm,
        memory=memory,
        search_tool=search_tool,
        retriever=retriever_tool,
    )
    rag = AgentFactory.create_rag(
        llm=llm,
        retriever=retriever,
        memory=memory,
    )

    # Build graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("router", heuristic_route)
    graph.add_node("web_search_collect", WebSearchCollectNode(search_tool))
    graph.add_node("retriever_collect", RetrieverCollectNode(retriever_tool))
    graph.add_node("chat", chat.as_node())
    graph.add_node("code", code.as_node())
    graph.add_node("rag", rag.as_node())
    graph.add_node("report", report.as_node())

    # Set entry point
    graph.set_entry_point("router")

    edge_map = {
        "chat": "chat",
        "code": "code",
        "rag": "rag",
        "report": "report",
        "web_search_collect": "web_search_collect",
        "retriever_collect": "retriever_collect",
        "__end__": END,
    }

    graph.add_conditional_edges("router", route_to_next_task, edge_map)
    for node_name in (
        "web_search_collect",
        "retriever_collect",
        "chat",
        "code",
        "rag",
        "report",
    ):
        graph.add_conditional_edges(node_name, route_to_next_task, edge_map)

    checkpointer = MemorySaver()

    logger.info(
        "graph_built",
        nodes=[
            "router",
            "web_search_collect",
            "retriever_collect",
            "chat",
            "code",
            "rag",
            "report",
        ],
    )

    return graph.compile(checkpointer=checkpointer)
