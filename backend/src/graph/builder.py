"""LangGraph graph builder."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.core.logging import get_logger
from src.graph.edges import route_from_router
from src.graph.state import AgentState

logger = get_logger(__name__)


def build_graph(container):
    """Build and compile the multi-agent graph.

    Graph flow:
    START → heuristic_router (no LLM) → {chat | code | report} → END

    Args:
        container: DI container with all dependencies

    Returns:
        Compiled LangGraph
    """
    from src.agents.factory import AgentFactory
    from src.graph.router import heuristic_route
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

    # Build graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("router", heuristic_route)
    graph.add_node("chat", chat.as_node())
    if code:
        graph.add_node("code", code.as_node())
    if report:
        graph.add_node("report", report.as_node())

    # Set entry point
    graph.set_entry_point("router")

    # router → each agent based on next_agent field
    edge_map = {"chat": "chat", "__end__": END}
    if code:
        edge_map["code"] = "code"
    if report:
        edge_map["report"] = "report"

    graph.add_conditional_edges("router", route_from_router, edge_map)

    # All agents → END (no supervisor loop)
    graph.add_edge("chat", END)
    if code:
        graph.add_edge("code", END)
    if report:
        graph.add_edge("report", END)

    checkpointer = MemorySaver()

    logger.info(
        "graph_built",
        nodes=["router", "chat"]
        + (["code"] if code else [])
        + (["report"] if report else []),
    )

    return graph.compile(checkpointer=checkpointer)
