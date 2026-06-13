# AI Agent Chatbot - Comprehensive Project Summary

## Executive Overview

A production-ready **LangGraph-based single-assistant Agentic RAG chatbot system** with advanced features including:
- A unified `AssistantAgent` for chat turns, memory, evidence orchestration, and final answers
- Agentic Research Evidence collection through `web_search` and `retriever`
- Retrieval-Augmented Generation (RAG) with Pinecone vector DB
- Real-time SSE streaming responses
- 3-tier memory architecture (session/topic/user)
- Full-stack deployment (Render + Vercel, zero-cost)
- Python FastAPI backend + TypeScript Next.js frontend

---

## 1. OVERALL TECH STACK

### Frontend
| Component | Technology | Version |
|-----------|-----------|---------|
| Framework | Next.js | 16.1.6 |
| Language | TypeScript | 5.9.3 |
| Styling | Tailwind CSS | 4.x |
| State Management | Zustand | 5.0.11 |
| UI Components | Radix UI + shadcn/ui | 1.4.3 |
| Markdown Rendering | react-markdown | 10.1.0 |
| XSS Protection | DOMPurify | 3.3.1 |
| Code Highlighting | highlight.js | 11.11.1 |
| Animations | Framer Motion | 12.34.0 |
| File Upload | react-dropzone | 15.0.0 |
| Icons | Lucide React | 0.564.0 |

### Backend
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Runtime | Python | 3.12 |
| Web Framework | FastAPI | 0.115+ |
| Server | Uvicorn | 0.32+ |
| Agent Orchestration | LangGraph | 0.2+ |
| AI Framework | LangChain | 0.3+ |
| LLM Providers | OpenRouter, OpenAI-compatible, Anthropic | Various |
| Config Management | Pydantic Settings | 2.0+ |
| Streaming | sse-starlette | 2.1+ |
| DI Container | dependency-injector | 4.41+ |
| Logging | structlog | 24.0+ |

### Data & Storage
| Component | Service | Use Case |
|-----------|---------|----------|
| Vector DB | Pinecone | RAG embeddings (multilingual-e5-large) |
| Session Memory | Upstash Redis / Redis | Short-term (TTL: 1 hour) |
| User/Topic Storage | Supabase PostgreSQL | Long-term persistent memory |
| Tracing (Optional) | LangSmith | LLM observability |

### Document Processing
| Format | Library | Features |
|--------|---------|----------|
| PDF | pdfplumber | Text + table extraction |
| DOCX | python-docx | Ordered heading, paragraph, table support |
| TXT/MD/CSV/JSON | Built-in | Markdown-like canonical parsing, table preservation |
| Embedding | Pinecone SDK | Async embedding generation |
| Chunking | Custom | Hierarchy-aware parent-child chunks with heading/page/table metadata |

### Deployment Infrastructure
| Environment | Frontend | Backend | Hosting |
|-------------|----------|---------|---------|
| Local | Docker (Next.js) | Docker (FastAPI) | localhost:3000/8000 |
| Production | Vercel | Render Free Tier | https://ai-agent-chatbot-iota.vercel.app |
| CI/CD | GitHub Actions | GitHub Actions | - |
| Cost | Free tier | Free tier (512MB RAM) | **$0/month total** |

---

## 2. KEY FEATURES & CAPABILITIES

### Assistant Agent Orchestration
**1 user-facing assistant agent** orchestrated by a minimal LangGraph state graph:

| Component | Role | Capabilities |
|-----------|------|--------------|
| **AssistantAgent** | Chat turn owner | Memory commands, context awareness, evidence-aware final response |
| **ResearchEvidenceCollector** | Evidence planner/executor | Chooses `web_search`, `retriever`, both, or neither; normalizes confidence and sources |

Research tools:

| Tool | Role | LLM Call |
|------|------|----------|
| **web_search** | Tavily result collection | No |
| **retriever** | Pinecone document retrieval | No |

LLM call count by path:

- Ordinary chat: final AssistantAgent response = 1 call
- Web/RAG/report: tool decision + final AssistantAgent response = 2 calls, plus external tool calls

### Memory System (3-Tier Architecture)
```
Session Memory (Redis, TTL: 1 hour)
    ↓ [Auto-trigger: >2000 tokens or >20 messages]
Topic Memory (Supabase, deleted with session)
    ↓ [Fact extraction]
User Memory (Supabase, permanent)
    └─ user_profiles: Preferences, user info
    └─ user_facts: Atomic facts ("loves coffee")
```

**Memory Commands** (Korean):
- `기억해:` / `기억해줘:` — Save user info
- `알고 있니?` — Query stored memory
- `잊어줘:` — Delete memory
- `요약해줘` — Generate conversation summary

### Document Management
- **Supported formats**: PDF, DOCX, TXT, MD, CSV, JSON
- **Max size**: 10MB
- **Processing pipeline**:
  1. File validation (magic bytes, MIME, size)
  2. Layout-aware parsing into canonical Markdown-like elements
  3. Heading/table/page metadata and parse quality warnings
  4. Hierarchy-aware parent-child chunking
  5. Child chunk embedding → Pinecone vector store
  6. Child search → parent context hydration for final answers
- **Lifecycle UI**: upload, list, delete, parse warning, loading, and delete-in-progress states in the document dialog

### Real-Time Chat
- **SSE Streaming**: Token-by-token streaming with 100ms buffering
- **Smart Rendering**: Plain text during stream → markdown after completion
- **Assistant Visualization**: Single Assistant badge plus tool usage details
- **Tool Tracking**: Tool usage display (expandable)
- **Auto-scroll**: Smart scrolling with "scroll to bottom" button

### Security Features
**Input Validation**:
- Prompt injection detection (JAILBREAK, DATA_EXFILTRATION, PRIVILEGE_ESCALATION, TOOL_MANIPULATION, PROMPT_LEAK)
- File magic-byte verification
- XSS protection via DOMPurify (tag/attribute whitelist)
- Rate limiting (per-session, per-minute, daily)

**File Upload Security**:
- Magic byte validation (PDF: `%PDF`, DOCX: `PK`)
- MIME type matching
- Size limits (10MB)
- PII detection (email, phone, etc.)

**Frontend Security**:
- Guest-first `device_id` and `session_id` scoping
- Optional bearer token header support in the API client for future auth integration
- URL protocol validation for links

### Observability & Analytics
**Metrics Dashboard**:
- Backend health status
- Request volume (24h, 7d, 30d)
- Success/failure rates
- Token usage tracking
- Average response times
- Research Evidence usage, confidence, and tool counts
- Offline RAG evaluation JSONL runner with expected tools, sources, confidence, page, heading path, table answer coverage, and parent hydration checks
- CI gate support for minimum source-hit, answer-coverage, tool-match, confidence-pass, citation-page, heading-path, table-coverage, and parent-hydration rates

**Stored Metrics** (Supabase):
- `request_metrics`: Agent performance logs
- `session metadata`: Session tracking
- `user_profiles` & `user_facts`: User analytics

---

## 3. ARCHITECTURE

### System Architecture Diagram
```
┌─────────────────────────────────────────────────────────────────────┐
│                          Client Layer                               │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  Next.js 16 + TypeScript + Zustand + shadcn/ui              │   │
│   └─────────────────────────┬───────────────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────────────┘
                              │ HTTPS (REST + SSE)
┌─────────────────────────────▼───────────────────────────────────────┐
│                          API Gateway Layer                          │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  FastAPI (Python 3.12+)                                     │
│   │  - CORS / Exception / Logging Middleware                    │
│   │  - REST API + SSE Streaming                                 │
│   │  - Pydantic validation                                      │
│   └─────────────────────────┬───────────────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│                    Orchestration Layer                              │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  LangGraph StateGraph (Agentic AI)                          │
│   │  AssistantAgent                                              │   │
│   │    ├─ Conversation Memory                                    │   │
│   │    └─ ResearchEvidenceCollector                              │   │
│   │         ├─ web_search                                        │   │
│   │         └─ retriever                                         │   │
│   └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│                    Infrastructure Layer                             │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐                    │
│   │  Pinecone  │  │   Redis    │  │  Supabase  │                    │
│   │ (Vector DB)│  │  (Session) │  │(DB/Memory) │                    │
│   └────────────┘  └────────────┘  └────────────┘                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Backend Module Structure
```
backend/src/
├── agents/              # Single assistant + evidence collection
│   ├── assistant_agent.py      # Chat turn owner and final response
│   ├── research_evidence.py    # Tool planning, execution, normalization
│   ├── conversation_memory.py  # Memory command handling
│   ├── base.py                # Abstract base
│   └── factory.py             # Factory pattern
│
├── api/                 # REST API layer
│   ├── routes.py        # 15+ endpoints
│   ├── schemas.py       # 20+ Pydantic models
│   ├── middleware.py    # CORS, exception, logging
│   └── dependencies.py  # DI injection points
│
├── graph/               # LangGraph state machine
│   ├── state.py         # AgentState TypedDict
│   └── builder.py       # assistant → END graph construction
│
├── core/                # Core infrastructure
│   ├── config.py        # Settings management
│   ├── di_container.py  # Dependency injection
│   ├── protocols.py     # Protocol interfaces
│   ├── prompt_security.py  # Injection detection
│   ├── logging.py       # Structured logging
│   └── validators.py    # File & input validation
│
├── llm/                 # LLM abstraction
│   ├── factory.py       # LLMFactory pattern
│   ├── openai_provider.py   # OpenAI-compatible API (OpenRouter 포함)
│   ├── anthropic_provider.py # Claude API
│   └── ollama_provider.py    # Local LLM
│
├── memory/              # Session & long-term
│   ├── in_memory_store.py   # Development
│   ├── redis_store.py       # Production
│   └── long_term_memory.py  # Supabase
│
├── documents/           # RAG pipeline
│   ├── parser.py        # Multi-format parsing
│   ├── chunker.py       # Smart chunking
│   ├── pinecone_store.py    # Vector store
│   └── retriever_impl.py    # Semantic search
│
├── tools/               # Agent tools
│   ├── web_search.py    # Tavily integration
│   └── retriever.py     # Document search
│
└── observability/       # Metrics & tracing
    ├── metrics_store.py
    └── agent_metrics.py
```

### Frontend Component Architecture (69 TypeScript files)
```
RootLayout (layout.tsx)
└── TooltipProvider
    └── ChatPage
        ├── Header
        │   ├── HealthIndicator
        │   ├── Language toggle
        │   └── Theme toggle
        ├── Sidebar (sessions)
        └── Main
            ├── CombinedDocumentUpload
            │   └── DocumentList
            └── ChatContainer
                ├── MessageList
                │   ├── MessageBubble
                │   │   ├── AgentBadge
                │   │   ├── MarkdownRenderer
                │   │   └── ToolUsage
                │   └── TypingIndicator
                └── ChatInput
```

### API Endpoints (15+)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/chat` | ❌ | Sync chat response |
| POST | `/api/v1/chat/stream` | ❌ | SSE streaming chat |
| POST | `/api/v1/documents/upload` | ❌ | File upload (RAG, scoped by `device_id` + `session_id`) |
| GET | `/api/v1/documents` | ❌ | List documents scoped by `device_id` |
| GET | `/api/v1/sessions` | ❌ | Session list scoped by `device_id` |
| DELETE | `/api/v1/sessions/{id}` | ❌ | Session delete |
| DELETE | `/api/v1/sessions/{id}/full` | ❌ | Full cleanup |
| GET | `/api/v1/health` | ❌ | Health check |
| GET | `/api/v1/metrics/summary` | ❌ | Metrics summary |

---

## 4. FILE STRUCTURE OVERVIEW

### Total Codebase Size
- **Backend**: 99 Python files
- **Frontend**: 69 TypeScript files
- **Documentation**: 12 markdown files
- **Configuration**: docker-compose.yml, render.yaml, pyproject.toml, package.json, etc.

### Key Config Files
- **pyproject.toml**: Backend dependencies (50+ packages)
- **package.json**: Frontend dependencies (30+ packages)
- **docker-compose.yml**: Local dev (backend, frontend, redis, nginx)
- **.env.example**: 95+ environment variables
- **render.yaml**: Infrastructure as Code
- **tsconfig.json**: TypeScript strict mode
- **next.config.ts**: Next.js optimizations
- **tailwind.config.ts**: Tailwind customization

---

## 5. NOTABLE IMPLEMENTATION DETAILS

### Performance Optimizations

**Frontend**:
1. **Token Buffering (100ms)**: Stream tokens collected → flushed every 100ms or 500+ chars
2. **Dual Rendering**: Plain text during SSE → markdown after completion
3. **Code Block Auto-Collapse**: >30 lines automatically collapsed
4. **Scroll Optimization**: 150ms debounce + requestAnimationFrame
5. **Message Memoization**: Completed messages memoized to prevent re-renders

**Backend**:
1. **Fully Async**: FastAPI async routes + async LLM calls
2. **Efficient Vector Search**: Top-k=3 with namespace scoping
3. **Auto-Summarization**: Triggered at >2000 tokens
4. **Connection Pooling**: Redis, Supabase, HTTP pooling
5. **Token Estimation**: tiktoken for accurate counting
6. **Structured Output Fallback**: OpenRouter-compatible text JSON fallback when structured output is unavailable

### Security Implementation

**Prompt Injection Detection** (`core/prompt_security.py`):
- 5 attack categories: JAILBREAK, DATA_EXFILTRATION, PRIVILEGE_ESCALATION, TOOL_MANIPULATION, PROMPT_LEAK
- 4 severity levels: critical, error, warning, info
- Real-time frontend warnings

**File Upload Validation** (`core/validators.py`):
- Magic byte verification (PDF: `%PDF`, DOCX: `PK`, etc.)
- MIME type matching
- Size limits (10MB)
- Path traversal prevention
- PII detection (email, phone, SSN patterns)

**XSS Protection**:
- DOMPurify with custom whitelist config
- No `dangerouslySetInnerHTML`
- URL protocol validation (http/https only)
- Markdown sanitization

**Guest Session Isolation**:
- `device_id` identifies the browser guest identity
- `session_id` scopes chat turns and RAG documents
- Frontend auth screens and route guards are not active
- Session deletion clears session memory, session topic summaries, RAG documents, and the session row
- User facts/profile data are deleted only through explicit user memory deletion

### Design Patterns

**Protocol-Oriented Architecture**:
- Structural typing (no inheritance required)
- LLMProvider, MemoryStore, DocumentRetriever protocols

**Factory Pattern**:
- LLMFactory, AgentFactory
- Plugin-style registration: `@LLMFactory.register("openai")`

**Dependency Injection**:
- dependency-injector library
- Constructor injection in routes and agents

**State Machine** (LangGraph):
- AgentState as central state
- `assistant` is the only active graph node
- ResearchEvidenceCollector makes the tool-use decision inside the assistant turn
- Ordinary chat bypasses evidence planning and uses a single final LLM call

**Strategy Pattern** (Document Chunking):
- `auto`: Format detection
- `default`: Fixed 500-token windows
- `code`: Preserve code blocks
- `tabular`: Row-by-row for CSVs

### Advanced Features

**Agentic Research Workflow**:
- AssistantAgent receives every chat turn
- ResearchEvidenceCollector chooses `web_search`, `retriever`, both, or neither for explicit evidence requests
- Final answer is generated by AssistantAgent using normalized evidence context, confidence, and sources

**Auto-Summarization Trigger**:
- Token count > 2000 OR
- Message count > 20 OR
- Time since last summary > 10 minutes

**LangSmith Integration** (Optional):
- Full LLM call tracing
- Enabled via `OBSERVABILITY__LANGSMITH_TRACING=true`

---

## 6. DEPLOYMENT ARCHITECTURE

### Local Development
```
Docker Compose Services:
  ✓ backend (FastAPI:8000)
  ✓ frontend (Next.js:3000)
  ✓ redis (6379)
  ✓ nginx (80)
```

### Production (Zero-Cost Deployment)

**Frontend**: Vercel
- Free tier: 100GB/month traffic
- Auto-deploy on main branch
- Zero cold start

**Backend**: Render.com Free Tier
- 512MB RAM, 0.1 CPU
- 15-minute auto-sleep
- Minimal active tools for predictable memory use

**External Services**:
- Pinecone (Vector DB): Free tier ~1M vectors
- Upstash Redis (Session): Free tier ~10K requests/day
- Supabase (DB): Free tier ~500MB storage

**CI/CD**: GitHub Actions
```
On: Push to main
├── Backend Tests (ruff lint, pytest)
├── Research Evidence Eval (offline JSONL thresholds)
├── Frontend Tests (eslint, next build)
├── Security Scan (Trivy, npm audit)
└── Deploy (parallel to Render + Vercel)
```

---

## 7. DATABASE SCHEMA

### Supabase Tables

**user_profiles**: User info & preferences
**user_facts**: Atomic facts ("loves Python")
**topic_summaries**: Conversation topic summaries
**request_metrics**: Agent performance logs
**sessions**: Session metadata

### Pinecone Index

**Index**: `documents` (1024 dimensions, cosine metric)
**Metadata**: session_id, device_id, document_id, record_type, parent_id, child_id, filename, heading_path, page/page_end, section_type, parse quality summary

---

## 8. SCALABILITY & FUTURE IMPROVEMENTS

**Current Free Tier Constraints**:
- Render: 512MB RAM → keep active tool surface small
- Redis: 10K req/day → batch requests
- Pinecone: 1M vectors → namespace by session

**Production Scaling Path**:
1. Upgrade Render to Pro (2GB RAM, GPU)
2. Self-host Qdrant or upgrade Pinecone tier
3. Implement Redis caching layer
4. Add request deduplication
5. Use cheaper LLM models (GPT-4o-mini)
6. Implement sliding-window memory retention

---

## 9. KEY LEARNINGS

**From Development** (CLAUDE.md):

1. **GLM-5 Integration**: Anthropic-compatible API at `https://api.z.ai/api/anthropic`
2. **Supabase Keys**: Always use `service_role` (not `anon`) in backend
3. **3-Tier Memory**: Session (fast) → Topic (preserved) → User (permanent)
4. **Research Evidence**: Keeps web/RAG/report evidence planning inside the single assistant flow
5. **Token Accounting**: Use tiktoken for accuracy, log separately (input/output)

---

## 10. QUICK STATS

| Metric | Value |
|--------|-------|
| Backend Files | Python FastAPI/LangGraph modules |
| Frontend Files | 69 TypeScript |
| REST Endpoints | 15+ |
| Agents | 1 active (`assistant`) |
| Active Tools | 2 (`web_search`, `retriever`) |
| Database Tables | 5+ |
| Config Variables | Environment-driven |
| Supported Formats | 6 (PDF, DOCX, TXT, MD, CSV, JSON) |
| Deployment Cost | $0/month |
| Cold Start | 10-30s (Render free) |
| Token Auto-Summarize | 2000 tokens |
| Session TTL | 1 hour (Redis) |
| Memory Commands | 4 (Korean) |

---

## 11. GETTING STARTED

### Local Development
```bash
# Backend
cd backend
uv sync --group dev
uv run uvicorn src.main:app --reload

# Frontend
cd ../frontend
npm install
npm run dev

# Docker Compose (all services)
docker-compose up -d
```

### Deployment
- **Render**: Push to main → GitHub Actions triggers Render deploy
- **Vercel**: Push to main → GitHub Actions triggers Vercel deploy
- **Cost**: $0/month (free tier limits apply)

---

**Last Updated**: 2026-06-13
**Created for**: Portfolio PDF Presentation
**Ready for**: Deployment, Scaling, Feature Extensions
