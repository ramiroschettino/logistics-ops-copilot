"""RAG con busqueda hibrida: BM25 (palabras) + embeddings (significado).

Por que dos buscadores? Cada uno cubre la debilidad del otro:
- BM25 matchea palabras exactas: imbatible con codigos (MA-2026-00042, CPF,
  EDB), terminos raros y nombres. Pero no entiende parafraseo.
- Los embeddings entienden significado ("cuanta plata puede valer el paquete"
  encuentra "limite de valor declarado"), pero confunden codigos parecidos.

Los dos rankings se fusionan con RRF (Reciprocal Rank Fusion): cada documento
suma 1/(60 + posicion) en cada ranking. Solo importan las POSICIONES, no los
scores (que no son comparables entre sistemas distintos). Es el estandar de
fusion en buscadores hibridos por lo robusto y simple que es.

Sin GEMINI_API_KEY el indice funciona igual, solo con BM25 (degradacion
elegante: la demo offline y los tests no dependen de ninguna API).
"""
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from app import embeddings
from app.config import DOCS_DIR

RRF_K = 60  # constante estandar de RRF: amortigua el peso de los primeros puestos


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


def rrf_fuse(rankings: list[list[int]], k: int = RRF_K) -> list[int]:
    """Fusiona varios rankings (listas de indices, mejor primero) en uno solo.
    Cada aparicion aporta 1/(k + posicion). Devuelve indices ordenados."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for position, idx in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + position + 1)
    return sorted(scores, key=scores.get, reverse=True)


class DocsIndex:
    def __init__(self, docs_dir: Path = DOCS_DIR):
        self.chunks = _load_chunks(docs_dir)
        self._bm25 = BM25Okapi([_tokenize(f"{c.title} {c.text}") for c in self.chunks])
        # Indice denso: solo si hay API key. Una llamada (cacheada) por corpus.
        self._vectors: list[list[float]] | None = None
        if embeddings.available():
            try:
                self._vectors = embeddings.embed_documents(
                    [f"{c.title}\n{c.text}" for c in self.chunks]
                )
            except Exception:
                self._vectors = None  # sin red / error de API -> seguimos con BM25

    # ------------------------------------------------ rankings individuales

    def _bm25_ranking(self, query: str) -> list[int]:
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [i for i in ranked if scores[i] > 0]

    def _dense_ranking(self, query: str) -> list[int] | None:
        if self._vectors is None:
            return None
        try:
            q = embeddings.embed_query(query)
        except Exception:
            return None  # API caida en runtime -> degradar a BM25
        scores = [embeddings.cosine_similarity(q, v) for v in self._vectors]
        return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    # ------------------------------------------------------------- busqueda

    def search(self, query: str, k: int = 3, mode: str = "hybrid") -> list[dict]:
        """mode: 'hybrid' (default), 'bm25' o 'dense' (para comparar en eval)."""
        bm25_ranking = self._bm25_ranking(query)
        dense_ranking = self._dense_ranking(query) if mode != "bm25" else None

        if mode == "dense" and dense_ranking is not None:
            ranked, used = dense_ranking, "dense"
        elif dense_ranking is not None:
            ranked, used = rrf_fuse([bm25_ranking, dense_ranking]), "hybrid"
        else:
            ranked, used = bm25_ranking, "bm25"

        return [
            {"source": self.chunks[i].source, "title": self.chunks[i].title,
             "text": self.chunks[i].text, "retrieval": used}
            for i in ranked[:k]
        ]


_index: DocsIndex | None = None


def get_index() -> DocsIndex:
    """Singleton lazy: el indice se construye una sola vez por proceso."""
    global _index
    if _index is None:
        _index = DocsIndex()
    return _index
