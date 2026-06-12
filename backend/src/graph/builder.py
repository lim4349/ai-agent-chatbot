"""LangGraph graph builder."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.core.logging import get_logger
from src.graph.state import AgentState

logger = get_logger(__name__)


def build_graph(container):
    """Build and compile the assistant graph.

    Graph flow:
    START → assistant → END

    Args:
        container: DI container with all dependencies

    Returns:
        Compiled LangGraph
    """
    from src.agents.factory import AgentFactory

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

    # Create the user-facing assistant using factory with resolved dependencies.
    assistant = AgentFactory.create_assistant(
        llm=llm,
        memory=memory,
        long_term_memory=long_term_memory,
        user_profiler=user_profiler,
        topic_memory=topic_memory,
        summarizer=summarizer,
        search_tool=search_tool,
        retriever=retriever_tool,
    )

    # Build graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("assistant", assistant.as_node())

    # Set entry point
    graph.set_entry_point("assistant")
    graph.add_edge("assistant", END)

    checkpointer = MemorySaver()

    logger.info(
        "graph_built",
        nodes=["assistant"],
    )

    return graph.compile(checkpointer=checkpointer)
