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
    START → LLM router → {chat | research} → END

    Args:
        container: DI container with all dependencies

    Returns:
        Compiled LangGraph
    """
    from src.agents.factory import AgentFactory
    from src.graph.router import LLMRouterNode

    # Resolve providers to actual instances
    llm = container.llm()
    memory = container.memory()
    tool_registry = container.tool_registry()
    long_term_memory = container.long_term_memory()
    user_profiler = container.user_profiler()
    topic_memory = container.topic_memory()
    summarizer = container.summarizer()

    # Tool instances for research agent
    search_tool = tool_registry.get("web_search") if tool_registry else None
    retriever_tool = tool_registry.get("retriever") if tool_registry else None

    # Create agent instances using factory with resolved dependencies
    chat = AgentFactory.create_chat(
        llm=llm,
        memory=memory,
        long_term_memory=long_term_memory,
        user_profiler=user_profiler,
        topic_memory=topic_memory,
        summarizer=summarizer,
    )
    research = AgentFactory.create_research(
        llm=llm,
        memory=memory,
        search_tool=search_tool,
        retriever=retriever_tool,
    )

    # Build graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("router", LLMRouterNode(llm))
    graph.add_node("chat", chat.as_node())
    graph.add_node("research", research.as_node())

    # Set entry point
    graph.set_entry_point("router")

    edge_map = {
        "chat": "chat",
        "research": "research",
        "__end__": END,
    }

    graph.add_conditional_edges("router", route_to_next_task, edge_map)
    graph.add_edge("chat", END)
    graph.add_edge("research", END)

    checkpointer = MemorySaver()

    logger.info(
        "graph_built",
        nodes=["router", "chat", "research"],
    )

    return graph.compile(checkpointer=checkpointer)
