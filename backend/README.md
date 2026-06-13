# AI Agent Chatbot - Backend

FastAPI 기반 AI 챗봇 백엔드 서버

현재 LangGraph 구성은 `AssistantAgent → END`입니다.
`AssistantAgent`는 대화와 메모리를 처리하고, 필요할 때 `ResearchEvidenceCollector`를 통해 `web_search`와 `retriever` 도구를 선택해 사용합니다.

RAG Document Lifecycle은 업로드 파일을 layout-aware Markdown-like 구조로 파싱하고, heading/table/page metadata를 보존한 뒤 parent-child retrieval record로 Pinecone에 저장합니다. 검색은 child chunk로 정밀하게 수행하고, 답변 컨텍스트는 parent chunk를 hydrate해서 제공합니다.

## 문서

- [백엔드 개발 가이드](./AGENTS.md) - 상세 개발 문서 및 프로젝트 룰
- [메인 README](../README.md) - 전체 프로젝트 개요

## 빠른 시작

```bash
uv sync --group dev
uv run uvicorn src.main:app --reload
```

API 문서: http://localhost:8000/docs

## 검증

```bash
uv run --with ruff ruff check .
uv run --with pytest --with pytest-asyncio --with pytest-cov --with pytest-timeout python -m pytest -q
uv run python -m src.evaluation.rag_eval evals/research_golden.jsonl \
  --min-source-hit-rate 1.0 \
  --min-answer-coverage-rate 1.0 \
  --max-no-answer-rate 0.0 \
  --min-tool-match-rate 1.0 \
  --min-confidence-pass-rate 1.0 \
  --min-citation-page-hit-rate 1.0 \
  --min-heading-path-hit-rate 1.0 \
  --min-table-answer-coverage-rate 1.0 \
  --min-parent-hydration-rate 1.0 \
  --min-evidence-item-source-hit-rate 1.0 \
  --min-evidence-snippet-coverage-rate 1.0
```

`evals/research_golden.jsonl`은 Research Evidence가 기대 도구, 출처, confidence, citation page, heading path, table answer coverage, parent hydration, normalized evidence item, snippet term 기준을 만족하는지 확인하는 offline 회귀 데이터셋입니다.
`PINECONE_API_KEY`와 `PINECONE_INDEX_NAME`이 있으면 실제 Pinecone Adapter를 사용하는 RAG Document Lifecycle smoke test도 실행됩니다.
