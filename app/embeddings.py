"""Embeddings densos via API de Gemini (gemini-embedding-001, free tier).

Que es un embedding: una lista de numeros (aca, 768) que representa el
SIGNIFICADO de un texto. Textos que significan lo mismo -> vectores parecidos,
aunque no compartan ninguna palabra. La red neuronal que los genera corre en
los servidores de Google: esta maquina solo guarda y compara listas de numeros.

Dos optimizaciones de costo/latencia:
- Cache en disco: los embeddings del corpus se calculan UNA vez por contenido
  (hash). Por consulta solo se pide 1 embedding: el de la pregunta.
- task_type: Gemini optimiza el vector segun el rol del texto
  (RETRIEVAL_DOCUMENT para el corpus, RETRIEVAL_QUERY para la pregunta).
"""
import hashlib
import json
import math

import httpx

from app.config import BASE_DIR, GEMINI_API_KEY

EMBED_MODEL = "gemini-embedding-001"
DIMENSIONS = 768  # truncamos de 3072 a 768: 4x menos espacio, calidad casi igual
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
CACHE_PATH = BASE_DIR / "data" / "embeddings_cache.json"


def available() -> bool:
    return bool(GEMINI_API_KEY)


def _normalize(vec: list[float]) -> list[float]:
    """Lleva el vector a largo 1. Al truncar dimensiones Gemini no garantiza
    vectores normalizados, y normalizar permite comparar con un simple producto punto."""
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Similitud de coseno entre vectores ya normalizados = producto punto.
    1.0 = mismo significado, ~0 = nada que ver."""
    return sum(x * y for x, y in zip(a, b))


def _embed_batch(texts: list[str], task_type: str) -> list[list[float]]:
    payload = {
        "requests": [
            {
                "model": f"models/{EMBED_MODEL}",
                "content": {"parts": [{"text": t}]},
                "taskType": task_type,
                "outputDimensionality": DIMENSIONS,
            }
            for t in texts
        ]
    }
    response = httpx.post(
        f"{API_BASE}/{EMBED_MODEL}:batchEmbedContents",
        params={"key": GEMINI_API_KEY},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return [_normalize(e["values"]) for e in response.json()["embeddings"]]


def embed_query(text: str) -> list[float]:
    """Embedding de una consulta de usuario (1 llamada chica por pregunta)."""
    return _embed_batch([text], "RETRIEVAL_QUERY")[0]


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embeddings del corpus, con cache en disco: si los textos no cambiaron
    (mismo hash), no se llama a la API."""
    content_hash = hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if cache.get("hash") == content_hash:
            return cache["vectors"]

    vectors = _embed_batch(texts, "RETRIEVAL_DOCUMENT")
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps({"hash": content_hash, "model": EMBED_MODEL, "vectors": vectors}),
        encoding="utf-8",
    )
    return vectors
