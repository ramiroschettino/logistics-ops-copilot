"""RAG liviano: indice BM25 sobre los markdown de docs/.

Se eligio BM25 (rank-bm25, puro Python) en lugar de embeddings densos para
que el sistema corra en cualquier maquina sin GPU ni descarga de modelos.
El chunking es por seccion (##), que en docs normativos preserva la unidad
semantica mejor que un split por tamano fijo.
"""
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from app.config import DOCS_DIR


@dataclass
class Chunk:
    source: str   # archivo de origen
    title: str    # titulo de la seccion
    text: str


def _normalize(text: str) -> str:
    """lowercase + sin acentos, para que 'aduanas' matchee 'Aduanas' y 'México' 'mexico'."""
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _normalize(text))


def _load_chunks(docs_dir: Path) -> list[Chunk]:
    chunks = []
    for path in sorted(docs_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        doc_title = content.splitlines()[0].lstrip("# ").strip()
        # split por secciones de nivel 2
        sections = re.split(r"^## ", content, flags=re.MULTILINE)[1:]
        for section in sections:
            title, _, body = section.partition("\n")
            chunks.append(Chunk(
                source=path.name,
                title=f"{doc_title} > {title.strip()}",
                text=body.strip(),
            ))
    return chunks


class DocsIndex:
    def __init__(self, docs_dir: Path = DOCS_DIR):
        self.chunks = _load_chunks(docs_dir)
        self._bm25 = BM25Okapi([_tokenize(f"{c.title} {c.text}") for c in self.chunks])

    def search(self, query: str, k: int = 3) -> list[dict]:
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [
            {"source": self.chunks[i].source, "title": self.chunks[i].title,
             "text": self.chunks[i].text, "score": round(float(scores[i]), 3)}
            for i in ranked if scores[i] > 0
        ]


_index: DocsIndex | None = None


def get_index() -> DocsIndex:
    """Singleton lazy: el indice se construye una sola vez por proceso."""
    global _index
    if _index is None:
        _index = DocsIndex()
    return _index
