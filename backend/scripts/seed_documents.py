"""Script to seed sample documents for RAG testing."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import get_config
from src.core.logging import setup_logging


async def seed_documents():
    """Seed sample documents to the vector store."""
    setup_logging(log_level="INFO")

    config = get_config()

    # Sample documents about LangGraph
    documents = [
        {
            "content": """LangGraph is a library for building stateful, multi-actor applications with LLMs.
It extends LangChain with graph-based orchestration, allowing you to define complex workflows
with cycles, branches, and persistent state. Key concepts include:
- State: A shared data structure passed between nodes
- Nodes: Functions that process the state
- Edges: Connections between nodes, which can be conditional""",
            "metadata": {"source": "langgraph_intro.md", "category": "introduction"},
        },
        {
            "content": """To create a LangGraph, you need to:
1. Define a State TypedDict with your data fields
2. Create node functions that take and return State
3. Build a StateGraph and add nodes
4. Add edges (including conditional edges)
5. Compile the graph with an optional checkpointer

Example:
```python
from langgraph.graph import StateGraph, END

graph = StateGraph(MyState)
graph.add_node("node1", node1_func)
graph.add_edge("node1", END)
app = graph.compile()
```""",
            "metadata": {"source": "langgraph_usage.md", "category": "tutorial"},
        },
        {
            "content": """Supervisor pattern in multi-agent systems:
The supervisor pattern uses a central coordinator agent that routes requests
to specialist agents. The supervisor analyzes the user's intent and selects
the most appropriate agent to handle the request.

Benefits:
- Clear separation of concerns
- Easy to add new specialist agents
- Centralized routing logic
- Better error handling

Implementation: Use conditional edges based on the supervisor's decision.""",
            "metadata": {"source": "multi_agent.md", "category": "architecture"},
        },
        {
            "content": """Dependency Injection in Python:
Using Protocol classes from typing module allows for structural subtyping.
This means any class that implements the Protocol's methods is considered
a valid subtype, enabling easy testing and flexible architecture.

Benefits:
- Easy to mock in tests
- Loose coupling between components
- Clear interface contracts
- Framework-agnostic

Example:
```python
from typing import Protocol

class LLMProvider(Protocol):
    async def generate(self, messages: list) -> str: ...
```""",
            "metadata": {"source": "di_patterns.md", "category": "best_practices"},
        },
    ]

    print("Seeding documents...")
    print(f"Collection: {config.rag.collection_name}")

    try:
        # Import chromadb and create embeddings
        import chromadb
        from langchain_openai import OpenAIEmbeddings

        # Initialize ChromaDB
        client = chromadb.Client()
        collection = client.get_or_create_collection(config.rag.collection_name)

        # Initialize embeddings
        embeddings = OpenAIEmbeddings(model=config.rag.embedding_model)

        # Generate embeddings and add to collection
        texts = [doc["content"] for doc in documents]
        embedding_vectors = await embeddings.aembed_documents(texts)

        collection.add(
            documents=texts,
            embeddings=embedding_vectors,
            metadatas=[doc["metadata"] for doc in documents],
            ids=[f"doc_{i}" for i in range(len(documents))],
        )

        print(f"Successfully seeded {len(documents)} documents!")

    except Exception as e:
        print(f"Error seeding documents: {e}")
        print("Note: Make sure OPENAI_API_KEY is set for embeddings")
        return 1

    return 0


if __name__ == "__main__":
    exit(asyncio.run(seed_documents()))
