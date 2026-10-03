"""Search over the home's rules: selected F-tags and the Evergreen handbook.

Embeddings run locally (ADR-0015). Every passage carries its source label,
which the assistant must cite, e.g. [F563] or [Handbook: Visiting].
"""

from __future__ import annotations

import os
import re
from functools import cache
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
CHUNK_CHARS = 1200
# Filters only clearly unrelated passages. Scores alone cannot separate
# in-scope from out-of-scope questions (see docs/iterations/9.3-rules-search-citations.md),
# so the model must still judge whether the passages answer the question.
MIN_SCORE = 0.6
NOTHING_FOUND = "No rule or policy matches this question."


class LocalEmbeddings(Embeddings):
    """Embeddings computed on this machine with fastembed (no API calls)."""

    def __init__(self, cache_dir: str | None = None) -> None:
        """Load the embedding model, downloading it on first use."""
        from fastembed import TextEmbedding

        self._model = TextEmbedding(EMBEDDING_MODEL, cache_dir=cache_dir)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed passages."""
        return [vector.tolist() for vector in self._model.passage_embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query."""
        return [float(x) for x in next(iter(self._model.query_embed(text)))]


def index_path() -> Path:
    """Return the saved index file, from CAREDESK_RULES_INDEX or the default."""
    return Path(os.environ.get("CAREDESK_RULES_INDEX", "data/rules_index.json"))


def model_cache_dir() -> str:
    """Return where the embedding model is stored, so it is downloaded once."""
    return os.environ.get("CAREDESK_MODEL_CACHE", "data/models")


def _paragraph_chunks(text: str) -> list[str]:
    """Group paragraphs into chunks of at most about CHUNK_CHARS characters."""
    chunks: list[str] = []
    current = ""
    for paragraph in (p.strip() for p in text.split("\n\n")):
        if not paragraph:
            continue
        if current and len(current) + len(paragraph) > CHUNK_CHARS:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks


def load_corpus(corpus_dir: Path) -> list[Document]:
    """Split the F-tags and the handbook into labelled passages."""
    documents: list[Document] = []
    for path in sorted((corpus_dir / "ftags").glob("F*.md")):
        title_line, _, body = path.read_text().partition("\n")
        tag = path.stem
        title = title_line.removeprefix(f"# {tag} — ").strip()
        body = re.sub(r"^Source:.*?\n.*?\n", "", body.lstrip(), count=1, flags=re.S)
        for chunk in _paragraph_chunks(body):
            documents.append(
                Document(page_content=chunk, metadata={"source": tag, "title": title})
            )

    handbook = (corpus_dir / "handbook.md").read_text()
    for section in re.split(r"^## ", handbook, flags=re.M)[1:]:
        heading, _, body = section.partition("\n")
        source = f"Handbook: {heading.strip()}"
        for chunk in _paragraph_chunks(body):
            documents.append(
                Document(
                    page_content=chunk, metadata={"source": source, "title": heading}
                )
            )
    return documents


def build_index(
    documents: list[Document], embeddings: Embeddings
) -> InMemoryVectorStore:
    """Embed the passages into an in-memory vector store."""
    store = InMemoryVectorStore(embedding=embeddings)
    store.add_documents(documents)
    return store


@cache
def _store() -> InMemoryVectorStore:
    path = index_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Rules index not found at {path}. Build it with: "
            "uv run python scripts/build_rules_index.py"
        )
    return InMemoryVectorStore.load(str(path), LocalEmbeddings(model_cache_dir()))


def search(
    query: str, k: int = 4, store: InMemoryVectorStore | None = None
) -> list[tuple[Document, float]]:
    """Return up to k passages scoring at least MIN_SCORE, best first."""
    hits = (store or _store()).similarity_search_with_score(query, k=k)
    return [(doc, score) for doc, score in hits if score >= MIN_SCORE]


def format_passages(hits: list[tuple[Document, Any]]) -> str:
    """Render passages with the source label the assistant must cite."""
    if not hits:
        return NOTHING_FOUND
    return "\n\n".join(
        f"[{doc.metadata['source']}] {doc.metadata['title']}\n{doc.page_content}"
        for doc, _ in hits
    )
