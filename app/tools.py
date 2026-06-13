"""Tools que los agentes pueden invocar (y que el servidor MCP re-expone).

Cada tool es una funcion Python normal + su schema JSON para tool-use del LLM.
La logica de negocio determinisitica (clasificar excepcion, decidir accion) vive
aca y no en el prompt: el LLM decide CUANDO usarla, el codigo garantiza QUE hace.
"""
from datetime import datetime

from app import db
from app.rag import get_index

# ---------------------------------------------------------------- tools

def get_shipment(tracking_number: str) -> dict:
    """Estado actual de un envio + historial de eventos."""
    shipment = db.get_shipment(tracking_number)
    if not shipment:
        return {"error": f"No existe el envio {tracking_number}"}
    events = db.get_events(tracking_number)
    last = events[-1] if events else None
    days_since_last = None
    if last:
        days_since_last = round(
            (db.DATASET_NOW - datetime.fromisoformat(last["occurred_at"])).total_seconds() / 86400, 1
        )
    return {"shipment": shipment, "events": events, "days_since_last_event": days_since_last}


def find_stuck_shipments(min_days_stuck: int = 4, limit: int = 10) -> dict:
    """Envios sin movimiento hace N dias (umbral 'stuck' del SLA: 4 dias)."""
    stuck = db.find_stuck_shipments(min_days_stuck, limit)
    return {"count": len(stuck), "shipments": stuck}


def classify_exception(tracking_number: str) -> dict:
    """Diagnostica el tipo de excepcion de un envio a partir de su tracking."""
    data = get_shipment(tracking_number)
    if "error" in data:
        return data
    ship, events = data["shipment"], data["events"]
    days = data["days_since_last_event"] or 0
    last_code = events[-1]["event_code"] if events else None

    if ship["status"] == "delivered":
        return {"tracking_number": ship["tracking_number"], "exception": None,
                "diagnosis": "Envio entregado, sin excepcion."}
    if last_code == "EDB":
        exc = "customs_hold"
    elif last_code == "EMH":
        exc = "invalid_address"
    elif days >= 30:
        exc = "lost_in_transit"
    elif days >= 4:
        exc = "carrier_delay"
    else:
        return {"tracking_number": ship["tracking_number"], "exception": None,
                "diagnosis": f"En transito normal (ultimo evento hace {days} dias)."}
    return {
        "tracking_number": ship["tracking_number"],
        "exception": exc,
        "days_stuck": days,
        "last_event": events[-1] if events else None,
        "destination_country": ship["destination_country"],
        "declared_value_usd": ship["declared_value_usd"],
    }


# Acciones posibles del agente de excepciones (enum cerrado = decision auditable)
ACTIONS = {
    "customs_hold": ("request_docs", "Solicitar factura al seller y documento fiscal al comprador en 24h; escalar a aduanas si no llega en 72h."),
    "invalid_address": ("notify_buyer", "Contactar al comprador con link de correccion de direccion (max 2 intentos en 5 dias)."),
    "carrier_delay": ("retry_delivery", "Reinyectar en la proxima ventana del carrier; si supera 7 dias, reasignar a carrier alternativo."),
    "lost_in_transit": ("mark_lost", "Iniciar busqueda formal con el carrier y abrir expediente de indemnizacion."),
}


def _action_for(exception_type: str, declared_value_usd: float) -> dict:
    """Logica pura del playbook (deterministica, testeable)."""
    if exception_type not in ACTIONS:
        return {"action": "escalate", "rationale": "Excepcion fuera del playbook: requiere supervisor humano."}
    action, rationale = ACTIONS[exception_type]
    # Regla de escalamiento del playbook: alto valor siempre pasa por humano
    if declared_value_usd > 200:
        return {"action": "escalate",
                "rationale": f"Valor declarado USD {declared_value_usd} > 200: escalamiento obligatorio. "
                             f"Accion sugerida al supervisor: {action} ({rationale})"}
    return {"action": action, "rationale": rationale}


def decide_action(tracking_number: str) -> dict:
    """Diagnostica el envio y decide la accion operativa segun el playbook.

    Recibe SOLO el tracking: la excepcion y el valor declarado se leen de la
    base, nunca de argumentos del LLM. Motivo (bug real observado): el modelo
    paso un valor inventado (100 en vez de 26.33), lo que podria saltear el
    guardrail de escalamiento por alto valor. Datos criticos viajan por
    codigo, no por la "memoria" del modelo."""
    diag = classify_exception(tracking_number)
    if "error" in diag:
        return diag
    if not diag.get("exception"):
        return {"tracking_number": diag["tracking_number"], "action": None,
                "rationale": diag["diagnosis"]}
    return {**diag, **_action_for(diag["exception"], diag.get("declared_value_usd", 0))}


def search_docs(query: str, k: int = 3) -> dict:
    """Busca en la base de conocimiento (normativa aduanera, SLAs, playbook).

    `k` queda fijo en codigo (no lo decide el LLM): cuantos fragmentos traer es
    una constante de retrieval, no una decision del modelo. Se coerciona por si
    algun cliente lo pasa como string."""
    try:
        k = int(k)
    except (TypeError, ValueError):
        k = 3
    results = get_index().search(query, k)
    return {"results": results}


# ------------------------------------------------- registro + schemas

TOOL_FUNCTIONS = {
    "get_shipment": get_shipment,
    "find_stuck_shipments": find_stuck_shipments,
    "classify_exception": classify_exception,
    "decide_action": decide_action,
    "search_docs": search_docs,
}

TOOL_SCHEMAS = {
    "get_shipment": {
        "type": "function",
        "function": {
            "name": "get_shipment",
            "description": "Devuelve el estado actual y el historial de eventos de un envio por numero de tracking (formato MA-2026-XXXXX).",
            "parameters": {
                "type": "object",
                "properties": {"tracking_number": {"type": "string", "description": "Numero de tracking, ej: MA-2026-00042"}},
                "required": ["tracking_number"],
            },
        },
    },
    "find_stuck_shipments": {
        "type": "function",
        "function": {
            "name": "find_stuck_shipments",
            "description": "Lista envios atascados (sin eventos nuevos hace N dias). Util para monitoreo proactivo de la operacion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_days_stuck": {"type": "integer", "description": "Dias minimos sin movimiento (default 4)"},
                    "limit": {"type": "integer", "description": "Maximo de resultados (default 10)"},
                },
                "required": [],
            },
        },
    },
    "classify_exception": {
        "type": "function",
        "function": {
            "name": "classify_exception",
            "description": "Diagnostica el tipo de excepcion de un envio: customs_hold, invalid_address, carrier_delay o lost_in_transit.",
            "parameters": {
                "type": "object",
                "properties": {"tracking_number": {"type": "string"}},
                "required": ["tracking_number"],
            },
        },
    },
    "decide_action": {
        "type": "function",
        "function": {
            "name": "decide_action",
            "description": "Diagnostica un envio y decide la accion operativa segun el playbook: request_docs, notify_buyer, retry_delivery, mark_lost o escalate. El valor declarado y la excepcion se leen de la base automaticamente.",
            "parameters": {
                "type": "object",
                "properties": {"tracking_number": {"type": "string", "description": "Numero de tracking, ej: MA-2026-00042"}},
                "required": ["tracking_number"],
            },
        },
    },
    "search_docs": {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "Busca en la base de conocimiento interna: normativa aduanera de AR/BR/MX, SLAs por pais y playbook de excepciones. Devuelve fragmentos con su fuente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Consulta en lenguaje natural"},
                },
                "required": ["query"],
            },
        },
    },
}


def run_tool(name: str, arguments: dict) -> dict:
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"Tool desconocida: {name}"}
    try:
        return fn(**arguments)
    except TypeError as e:
        return {"error": f"Argumentos invalidos para {name}: {e}"}
