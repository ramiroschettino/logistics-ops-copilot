"""Evaluacion del sistema agentico (mini eval-set).

Mide dos cosas que NO dependen de la redaccion del LLM (eval robusta):
1. Routing accuracy: la consulta llega al agente correcto?
2. Tool accuracy: el agente invoco la tool esperada?

Corre en modo demo (deterministico) o live (Groq). Comparar ambos modos
permite detectar regresiones al cambiar de modelo o de prompt.

Uso: python eval/eval_agent.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.graph import ask  # noqa: E402

# (consulta, agente_esperado, tool_esperada)
EVAL_SET = [
    ("Donde esta el envio MA-2026-00042?", "tracking", "get_shipment"),
    ("Estado del paquete MA-2026-00150", "tracking", "get_shipment"),
    ("Necesito el historial de eventos de MA-2026-00007", "tracking", "get_shipment"),
    ("Que paquetes estan trabados y que hago con cada uno?", "exceptions", "decide_action"),
    ("Hay envios sin movimiento hace mas de una semana?", "exceptions", "find_stuck_shipments"),
    ("El envio MA-2026-00022 esta demorado, que accion tomamos?", "exceptions", "classify_exception"),
    ("Cual es el limite de valor para courier en Argentina?", "customs", "search_docs"),
    ("Que documentos pide Brasil para liberar una retencion?", "customs", "search_docs"),
    ("Cuanto tarda un envio express a Mexico segun el SLA?", "customs", "search_docs"),
    ("Cual es la politica de indemnizacion por extravio?", "customs", "search_docs"),
]


def main() -> int:
    route_hits = tool_hits = 0
    rows = []
    mode = None
    for query, expected_route, expected_tool in EVAL_SET:
        result = ask(query)
        mode = result["mode"]
        route_ok = result["agent_used"] == expected_route
        tool_ok = any(t["tool"] == expected_tool for t in result["tools_called"])
        route_hits += route_ok
        tool_hits += tool_ok
        rows.append((query[:52], result["agent_used"], "OK" if route_ok else "X",
                     "OK" if tool_ok else "X"))

    print(f"\nEval del Logistics Copilot (modo: {mode})\n" + "=" * 78)
    print(f"{'consulta':<54}{'agente':<12}{'ruta':<6}tool")
    for row in rows:
        print(f"{row[0]:<54}{row[1]:<12}{row[2]:<6}{row[3]}")
    n = len(EVAL_SET)
    print("=" * 78)
    print(f"Routing accuracy: {route_hits}/{n} ({100 * route_hits / n:.0f}%)")
    print(f"Tool accuracy:    {tool_hits}/{n} ({100 * tool_hits / n:.0f}%)")
    return 0 if route_hits == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
