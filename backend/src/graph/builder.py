"""LangGraph graph builder."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.core.logging import get_logger
from src.graph.edges import route_by_next_agent
from src.graph.state import AgentState

logger = get_logger(__name__)


def build_graph(container):
    """Build and compile the multi-agent graph.

    Graph flow:
    START → supervisor → {rag | web_search | code | chat} → END

    Args:
        container: DI container with all dependencies

    Returns:
        Compiled LangGraph
    """
    from src.agents.factory import AgentFactory

    # Create agent instances using factory
    supervisor = AgentFactory.create_supervisor(container)
    chat = AgentFactory.create_chat(container)
    code = AgentFactory.create_code(container)
    rag = AgentFactory.create_rag(container)
    web_search = AgentFactory.create_web_search(container)

    # Build graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("supervisor", supervisor.as_node())
    graph.add_node("chat", chat.as_node())
    graph.add_node("code", code.as_node())

    # Add optional nodes
    if rag:
        graph.add_node("rag", rag.as_node())
    if web_search:
        graph.add_node("web_search", web_search.as_node())

    # Set entry point
    graph.set_entry_point("supervisor")

    # Build conditional edges mapping
    edge_mapping = {
        "chat": "chat",
        "code": "code",
    }
    if rag:
        edge_mapping["rag"] = "rag"
    if web_search:
        edge_mapping["web_search"] = "web_search"

    # Add conditional edges from supervisor
    graph.add_conditional_edges(
        "supervisor",
        route_by_next_agent,
        edge_mapping,
    )

    # All specialist agents go to END
    graph.add_edge("chat", END)
    graph.add_edge("code", END)
    if rag:
        graph.add_edge("rag", END)
    if web_search:
        graph.add_edge("web_search", END)

    # Compile with memory saver for state persistence
    checkpointer = MemorySaver()

    logger.info(
        "graph_built",
        nodes=["supervisor", "chat", "code"] + (["rag"] if rag else []) + (["web_search"] if web_search else []),
    )

    return graph.compile(checkpointer=checkpointer)
