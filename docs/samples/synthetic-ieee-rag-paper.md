# A Synthetic Study on Evidence-Aware RAG Chunking

## Abstract

This synthetic paper evaluates hierarchy-aware chunking for enterprise RAG systems.

## Experiments

| Method | Table Question Hit Rate | Notes |
|---|---:|---|
| Flat chunks | 0.68 | loses heading context |
| Heading-aware parent-child retrieval | 0.86 | preserves section and table context |

Heading-aware parent-child retrieval improved table question hit rate compared with flat chunks.

## Limitations

The dataset is synthetic and intended for portfolio regression testing, not external benchmarking.
