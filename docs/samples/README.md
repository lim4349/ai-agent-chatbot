# Synthetic Sample Documents

These files are synthetic portfolio fixtures for testing and demonstrating the RAG pipeline.
They do not contain real Exem, Exemble, customer, or internal operational data.

Primary domain:
- IT operations, incident response, database performance, alert policy

Secondary domains:
- Release notes, security policy, HR-style policy, technical paper samples

The deterministic eval dataset in `backend/evals/research_golden.jsonl` references these
documents to exercise document summary, heading-aware retrieval, table/CSV retrieval,
abstention, web-only, and mixed RAG+web cases.
