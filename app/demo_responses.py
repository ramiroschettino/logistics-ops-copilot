"""Modo demo (sin API key / sin internet).

Las tools corren DE VERDAD contra la DB y el indice RAG; lo unico que se
reemplaza es el razonamiento del LLM, por plantillas deterministicas.
Asi la arquitectura completa se puede demostrar offline.
"""
import re

from app import tools


def _extract_tracking(message: str) -> str | None:
    m = re.search(r"MA-\d{4}-\d{5}", message.upper())
    return m.group(0) if m else None


def demo_tracking(message: str) -> tuple[str, list[dict]]:
    tracking = _extract_tracking(message)
    if not tracking:
        result = tools.find_stuck_shipments(min_days_stuck=0, limit=5)
        called = [{"tool": "find_stuck_shipments", "args": {"min_days_stuck": 0, "limit": 5}}]
        lines = ["No me pasaste un tracking (formato MA-2026-XXXXX). Envios con actividad reciente pendiente:"]
        lines += [f"- {s['tracking_number']} -> {s['destination_country']} | {s['last_event']}"
                  for s in result["shipments"]]
        return "\n".join(lines), called

    result = tools.get_shipment(tracking)
    called = [{"tool": "get_shipment", "args": {"tracking_number": tracking}}]
    if "error" in result:
        return result["error"], called
    s, events = result["shipment"], result["events"]
    last = events[-1]
    days = result["days_since_last_event"]
    if s["status"] == "delivered":
        health = "entregado, caso cerrado"
    elif (days or 0) < 4:
        health = "viene dentro de lo normal"
    else:
        health = f"ALERTA: sin movimiento hace {days} dias"
    answer = (
        f"Envio {s['tracking_number']} ({s['origin_country']} -> {s['destination_country']}, "
        f"{s['service_level']}, carrier {s['carrier']})\n"
        f"Estado: {s['status']} | Ultimo evento: {last['description']} en {last['location']} "
        f"hace {days} dias.\n"
        f"Evaluacion: {health}."
    )
    return answer, called


def demo_exceptions(message: str) -> tuple[str, list[dict]]:
    tracking = _extract_tracking(message)
    called: list[dict] = []

    if tracking:
        targets = [tracking]
    else:
        stuck = tools.find_stuck_shipments(min_days_stuck=4, limit=5)
        called.append({"tool": "find_stuck_shipments", "args": {"min_days_stuck": 4, "limit": 5}})
        targets = [s["tracking_number"] for s in stuck["shipments"]]
        if not targets:
            return "No hay envios atascados (>4 dias sin movimiento). Operacion saludable.", called

    lines = [f"Triage de excepciones ({len(targets)} envios):", ""]
    for tn in targets:
        diag = tools.classify_exception(tn)
        called.append({"tool": "classify_exception", "args": {"tracking_number": tn}})
        if "error" in diag:
            lines.append(f"- {tn}: {diag['error']}")
            continue
        if not diag.get("exception"):
            lines.append(f"- {tn}: {diag['diagnosis']}")
            continue
        decision = tools.decide_action(diag["exception"], diag.get("declared_value_usd", 0))
        called.append({"tool": "decide_action",
                       "args": {"exception_type": diag["exception"],
                                "declared_value_usd": diag.get("declared_value_usd", 0)}})
        lines.append(
            f"- {tn} ({diag['destination_country']}, USD {diag['declared_value_usd']}): "
            f"{diag['exception']} hace {diag['days_stuck']} dias -> ACCION: {decision['action']}\n"
            f"  Motivo: {decision['rationale']}"
        )
    return "\n".join(lines), called


def demo_customs(message: str) -> tuple[str, list[dict]]:
    result = tools.search_docs(message, k=2)
    called = [{"tool": "search_docs", "args": {"query": message, "k": 2}}]
    if not result["results"]:
        return "La base de conocimiento no cubre esa consulta.", called
    lines = []
    for r in result["results"]:
        lines.append(f"[{r['title']}]\n{r['text']}\n(Fuente: {r['source']})\n")
    return "\n".join(lines).strip(), called


DEMO_HANDLERS = {
    "tracking": demo_tracking,
    "exceptions": demo_exceptions,
    "customs": demo_customs,
}
