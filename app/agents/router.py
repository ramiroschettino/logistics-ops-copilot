"""Router: decide que agente especialista atiende cada consulta.

En modo real lo decide el LLM (clasificacion con salida restringida).
En modo demo usa heuristica por keywords, para que la demo funcione
sin API key. Misma interfaz en ambos casos.
"""
import re
import unicodedata

from app.llm import get_client

ROUTES = ("tracking", "exceptions", "customs")

ROUTER_PROMPT = """Sos el router de un sistema multiagente de logistica. \
Clasifica la consulta del usuario en exactamente una categoria:

- tracking: estado/ubicacion de un envio puntual, historial de eventos.
- exceptions: envios con problemas, atascados, demorados, retenidos; que accion tomar; monitoreo de la operacion.
- customs: preguntas sobre normativa aduanera, impuestos, limites de valor, SLAs, politicas de indemnizacion.

Responde UNICAMENTE con una palabra: tracking, exceptions o customs."""

_EXCEPTION_WORDS = ("trabado", "atascado", "stuck", "excepcion", "problema", "demorado",
                    "retenido", "que hago", "que accion", "frenado", "sin movimiento", "triage")
_CUSTOMS_WORDS = ("aduana", "limite", "impuesto", "arancel", "franquicia", "normativa",
                  "sla", "indemniza", "cpf", "cuit", "rfc", "restringido", "prohibido",
                  "cuanto tarda", "tiempo de entrega", "politica", "retencion",
                  "documento", "regulacion")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def route_by_keywords(message: str) -> str:
    """Heuristica del modo demo. Orden: excepciones > normativa > tracking."""
    text = _normalize(message)
    has_tracking_number = bool(re.search(r"ma-\d{4}-\d{5}", text))
    if any(w in text for w in _EXCEPTION_WORDS):
        return "exceptions"
    if any(w in text for w in _CUSTOMS_WORDS) and not has_tracking_number:
        return "customs"
    return "tracking"


def route_by_llm(message: str) -> str:
    msg = get_client().chat([
        {"role": "system", "content": ROUTER_PROMPT},
        {"role": "user", "content": message},
    ])
    answer = (msg.content or "").strip().lower()
    for r in ROUTES:
        if r in answer:
            return r
    return route_by_keywords(message)  # fallback defensivo
