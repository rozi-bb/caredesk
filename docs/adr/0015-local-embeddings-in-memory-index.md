# ADR-0015: Local embeddings and an in-memory vector index

- Status: Accepted
- Date: 2026-10-03

## Context

Rules search needs embeddings. The planned provider (OpenAI) has no credit. The corpus is small: 14 F-tags and a 9-section handbook, about 200 passages.

## Decision

- Embeddings: `BAAI/bge-small-en-v1.5` run locally through fastembed (ONNX, no PyTorch). The model is downloaded once into `data/models`.
- Index: LangChain's `InMemoryVectorStore`, built by `scripts/build_rules_index.py` and saved to `data/rules_index.json`.
- Search returns the top 5 passages above a cosine similarity of 0.6.

## Alternatives considered

- **OpenAI embeddings**: better quality, but needs credit and sends the corpus to an API on every rebuild.
- **A vector database (Chroma, pgvector)**: unnecessary for 200 passages; pgvector becomes natural once Postgres arrives in release 2.
- **Keyword search (BM25)**: no model to download, but misses paraphrases such as "come and see my mum late" for visiting rights.

## Consequences

- No API cost for embeddings; rebuilding the index takes about two minutes, most of it the first model download.
- The 0.6 threshold only removes clearly unrelated passages. Scores alone cannot tell an in-scope question from an out-of-scope one, so the system prompt makes the model judge whether the passages answer the question, and the groundedness evaluation checks it.
- Switching to API embeddings later means rebuilding the index and re-running the groundedness evaluation.
