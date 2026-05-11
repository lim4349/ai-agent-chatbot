# AI Agent Chatbot Context

This context names the core product concepts in the LangGraph-based chatbot so architecture seams use the same language as the domain.

## Language

**Chat Turn**:
One user message and the assistant response produced from it, including routing, session context, and streaming metadata.
_Avoid_: request handler, route logic

**Research Evidence**:
External or uploaded material collected before a research answer is generated.
_Avoid_: tool output, context blob

**RAG Document**:
A user-uploaded file parsed, chunked, embedded, and stored for session-scoped retrieval.
_Avoid_: file, vector record

**RAG Document Lifecycle**:
The full path a **RAG Document** follows from upload validation through retrieval or deletion.
_Avoid_: upload endpoint, document service

**Conversation Memory**:
Session, topic, and user-level information used to preserve conversational continuity.
_Avoid_: cache, history

**LLM Invocation**:
A single call to a configured model adapter, including cache lookup, response normalization, token usage, and structured-output parsing.
_Avoid_: provider call, model wrapper

**Session**:
A guest-device conversation container that owns chat messages and session-scoped uploaded documents.
_Avoid_: thread, room

## Relationships

- A **Session** contains many **Chat Turns**.
- A **Chat Turn** may use **Conversation Memory**.
- A **Chat Turn** may route to research and collect **Research Evidence**.
- **Research Evidence** may include chunks from **RAG Documents**.
- A **RAG Document Lifecycle** stores and removes **RAG Documents** within a **Session**.
- An **LLM Invocation** supports router, chat, research, summarization, and profiling behavior.

## Example dialogue

> **Dev:** "When a **Chat Turn** asks about an uploaded PDF, where should the retrieval rule live?"
> **Domain expert:** "In **Research Evidence**. The **Chat Turn** only prepares session context; **Research Evidence** decides that an explicit **RAG Document** question needs retrieval."

## Flagged ambiguities

- "document" can mean raw upload bytes, parsed sections, chunks, or stored vectors. Resolved: use **RAG Document** for the product concept and keep parser/chunker implementation terms local to the **RAG Document Lifecycle**.
- "memory" can mean Redis messages, Supabase user facts, summaries, or frontend feedback. Resolved: use **Conversation Memory** for the product concept and name the concrete adapter when storage matters.
