"""Build the rules search index from corpus/ into data/rules_index.json.

Embeddings run locally; the model is downloaded once into data/models.

Usage:
    uv run python scripts/build_rules_index.py
"""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

from agent.rules import (
    LocalEmbeddings,
    build_index,
    index_path,
    load_corpus,
    model_cache_dir,
)

CORPUS = Path(__file__).resolve().parent.parent / "corpus"


def main() -> None:
    """Chunk the corpus, embed it, and save the index."""
    started = time.time()
    documents = load_corpus(CORPUS)
    store = build_index(documents, LocalEmbeddings(model_cache_dir()))
    path = index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    store.dump(str(path))
    per_source = Counter(d.metadata["source"] for d in documents)
    print(
        f"Indexed {len(documents)} passages from {len(per_source)} sources into {path}"
    )
    for source, count in sorted(per_source.items()):
        print(f"  {source:<45}{count:>4}")
    print(f"Done in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
