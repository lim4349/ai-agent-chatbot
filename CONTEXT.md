# AI Agent Chatbot Context

This context names the core product concepts in the LangGraph-based chatbot so architecture seams use the same language as the domain.

## Language

**Chat Turn**:
One user message and the assistant response produced from it, including session context, optional evidence collection, and streaming metadata.
_Avoid_: request handler, route logic

**Assistant Agent**:
The single user-facing agent that owns a **Chat Turn**, handles **Conversation Memory**, decides whether **Research Evidence** is needed, and produces the final answer.
_Avoid_: chat agent, research agent

**Research Evidence**:
External or uploaded material collected before a research answer is generated.
_Avoid_: tool output, context blob

**RAG Document**:
A user-uploaded file parsed, chunked, embedded, and stored for session-scoped retrieval.
_Avoid_: file, vector record

**Parsed Document**:
The canonical Markdown-like layout representation produced from a **RAG Document** before chunking, including elements, heading paths, table Markdown, page references, and parse quality warnings.
_Avoid_: raw text, extracted text

**RAG Document Lifecycle**:
The session-scoped file upload path a **RAG Document** follows from upload validation through retrieval or deletion.
_Avoid_: upload endpoint, document service

**Parent-Child Retrieval**:
The retrieval strategy where small child chunks are embedded for precise vector search, then their parent context chunks are hydrated for the final answer.
_Avoid_: chunk overlap trick, bigger top-k

**Parse Quality**:
The page/table/element counts and warnings that describe whether a **Parsed Document** is trustworthy enough for RAG.
_Avoid_: upload status

**Conversation Memory**:
Session, topic, and user-level information used to preserve conversational continuity.
_Avoid_: cache, history

**Memory Lifecycle Policy**:
The deletion rules for **Conversation Memory** in a guest-first product.
Session deletion removes session-scoped messages, topic summaries, RAG documents, and the session row.
User memory deletion removes guest user facts/profile data and is a separate explicit action.
_Avoid_: auth policy, retention setting

**LLM Invocation**:
A single call to a configured model adapter, including cache lookup, response normalization, token usage, and structured-output parsing.
_Avoid_: provider call, model wrapper

**Session**:
A guest-device conversation container that owns chat messages and session-scoped uploaded documents.
_Avoid_: thread, room

## Relationships

- A **Session** contains many **Chat Turns**.
- An **Assistant Agent** handles each **Chat Turn**.
- A **Chat Turn** may use **Conversation Memory**.
- A **Chat Turn** may collect **Research Evidence**.
- **Research Evidence** may include chunks from **RAG Documents**.
- A **RAG Document** becomes a **Parsed Document** before chunking.
- A **RAG Document Lifecycle** stores and removes **RAG Documents** within a **Session**.
- A **RAG Document Lifecycle** uses **Parent-Child Retrieval** metadata so **Research Evidence** can search child chunks and answer from parent context.
- **Parse Quality** is produced during **RAG Document Lifecycle** ingestion and may be shown in upload/list responses.
- An **LLM Invocation** supports assistant response generation, evidence planning, summarization, and profiling behavior.
- A **Memory Lifecycle Policy** decides which **Conversation Memory** is deleted with a **Session** and which user-level facts require explicit user memory deletion.

## Example dialogue

> **Dev:** "When a **Chat Turn** asks about an uploaded PDF, where should the retrieval rule live?"
> **Domain expert:** "In **Research Evidence**. The **Chat Turn** only prepares session context; **Research Evidence** decides that an explicit **RAG Document** question needs retrieval."

## Flagged ambiguities

- "document" can mean raw upload bytes, parsed sections, chunks, or stored vectors. Resolved: use **RAG Document** for the product concept, **Parsed Document** for layout-aware parser output, and keep concrete parser/chunker/vector terms local to the **RAG Document Lifecycle**.
- "memory" can mean Redis messages, Supabase user facts, summaries, or frontend feedback. Resolved: use **Conversation Memory** for the product concept and name the concrete adapter when storage matters.
- "delete session" does not mean "delete all user personalization." Resolved: use **Memory Lifecycle Policy** and keep user facts/profile deletion behind `/api/v1/users/{user_id}/memory`.
