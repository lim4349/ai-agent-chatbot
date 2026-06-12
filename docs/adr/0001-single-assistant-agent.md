# ADR 0001: Use Single Assistant Agent With Evidence Tools

## Status

Accepted

## Context

The previous graph used an LLM router to choose between `chat` and `research`.
That added one LLM invocation to most Chat Turns while the `research` agent still
made a second tool decision internally. With only two active agent names, the
router did not provide enough leverage for its cost and failure surface.

The product direction is a cloud-hosted Agentic RAG application, not a
multi-specialist demo. The valuable behavior is evidence collection, quality
tracking, and stable operation.

## Decision

Use one **Assistant Agent** as the user-facing graph node.

The Assistant Agent handles Conversation Memory, collects Research Evidence when
needed, and produces the final answer. Web search and uploaded-document
retrieval remain tools behind the Research Evidence module.

## Consequences

- Chat Turns avoid an extra router LLM invocation.
- Research Evidence becomes the main place for tool selection, confidence, and
  source handling.
- Future specialized behavior should be added as tools or sub-agents only when
  it has distinct context, permissions, evaluation, or ownership needs.
