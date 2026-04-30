# AI Agent Chatbot - Backend

FastAPI 기반 AI 챗봇 백엔드 서버

현재 LangGraph 구성은 `LLMRouterNode → ChatAgent | ResearchAgent`입니다.
`ResearchAgent`는 필요할 때 `web_search`와 `retriever` 도구를 선택해 사용합니다.

## 문서

- [백엔드 개발 가이드](./AGENTS.md) - 상세 개발 문서 및 프로젝트 룰
- [메인 README](../README.md) - 전체 프로젝트 개요

## 빠른 시작

```bash
uv sync --group dev
uv run uvicorn src.main:app --reload
```

API 문서: http://localhost:8000/docs
