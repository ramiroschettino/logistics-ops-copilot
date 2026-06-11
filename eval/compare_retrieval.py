"""Comparador de retrieval: BM25 vs embeddings vs hibrido, lado a lado.

Para QUE existe: ver con tus propios ojos cuando gana cada metodo.
- BM25 gana con codigos y terminos exactos ("evento EDB", "CPF").
- Los embeddings ganan con parafraseo ("cuanta plata puede valer el paquete"
  no comparte palabras con "limite de valor declarado").
- El hibrido (fusion RRF) saca lo mejor de ambos: es el estandar 2026.

Sin GEMINI_API_KEY solo corre la columna BM25 (el resto avisa).

Uso: python eval/compare_retrieval.py ["consulta propia"]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import embeddings  # noqa: E402
from app.rag import get_index  # noqa: E402

QUERIES = [
    # (consulta, que esperamos ver)
    ("limite de valor para courier en Argentina", "facil: ambos metodos aciertan"),
    ("cuanta plata puede valer el paquete que mando", "parafraseo: BM25 sufre, embeddings gana"),
    ("que significa el evento EDB", "termino exacto raro: BM25 gana"),
    ("el comprador no estaba en su casa, que hacemos", "semantica pura: embeddings gana"),
    ("documentos para liberar una retencion en Brasil", "mixta: el hibrido deberia rankear mejor"),
]


def top_titles(query: str, mode: str, k: int = 2) -> list[str]:
    results = get_index().search(query, k=k, mode=mode)
    if results and results[0]["retrieval"] != mode:
        return [f"(no disponible: cayo a {results[0]['retrieval']})"]
    return [r["title"] for r in results] or ["(sin resultados)"]


def main() -> None:
    queries = [(sys.argv[1], "consulta propia")] if len(sys.argv) > 1 else QUERIES

    if not embeddings.available():
        print("AVISO: sin GEMINI_API_KEY solo se compara BM25.")
        print("Key gratis en https://aistudio.google.com -> agregarla al .env\n")

    for query, expectation in queries:
        print("=" * 78)
        print(f"CONSULTA: {query}")
        print(f"(esperado: {expectation})\n")
        for mode in ("bm25", "dense", "hybrid"):
            print(f"  [{mode}]")
            for i, title in enumerate(top_titles(query, mode), 1):
                print(f"    {i}. {title}")
        print()


if __name__ == "__main__":
    main()
