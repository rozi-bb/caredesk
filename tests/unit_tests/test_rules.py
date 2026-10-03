from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from agent import rules

CORPUS = Path(__file__).resolve().parents[2] / "corpus"
VOCABULARY = ["visit", "money", "fire"]


class KeywordEmbeddings(Embeddings):
    """Tiny deterministic embeddings: one dimension per vocabulary word."""

    def _vector(self, text: str) -> list[float]:
        return [1.0 if word in text.lower() else 0.0 for word in VOCABULARY] + [0.1]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def test_corpus_has_every_tag_and_handbook_section() -> None:
    sources = {d.metadata["source"] for d in rules.load_corpus(CORPUS)}
    assert {
        f"F{n}"
        for n in (550, 557, 559, 561, 563, 567, 578, 580, 583, 585, 600, 604, 609, 700)
    } <= sources
    assert "Handbook: Visiting" in sources and "Handbook: Contacts" in sources


def test_file_headers_are_not_indexed() -> None:
    documents = rules.load_corpus(CORPUS)
    assert not any("Surveyor procedures" in d.page_content for d in documents)
    assert not any(d.page_content.startswith("Source: CMS") for d in documents)


def test_search_keeps_only_passages_above_the_threshold() -> None:
    store = rules.build_index(
        [
            Document(
                "Visit hours and visit rights.",
                metadata={"source": "F563", "title": "Visitors"},
            ),
            Document(
                "Personal money accounts.",
                metadata={"source": "F567", "title": "Funds"},
            ),
        ],
        KeywordEmbeddings(),
    )
    hits = rules.search("Can I visit?", store=store)
    assert [d.metadata["source"] for d, _ in hits] == ["F563"]
    assert rules.search("fire drill", store=store) == []


def test_passages_are_labelled_for_citation() -> None:
    doc = Document(
        "Text.", metadata={"source": "Handbook: Visiting", "title": "Visiting"}
    )
    assert rules.format_passages([(doc, 0.9)]).startswith(
        "[Handbook: Visiting] Visiting"
    )
    assert rules.format_passages([]) == rules.NOTHING_FOUND
