"""Grafo de orquestacion multiagente (LangGraph).

Topologia: router -> {tracking | exceptions | customs} -> critic -> END
                          ^                                  |
                          └――――― REVISAR (max 1 vez) ――――――――┘

El estado fluye por el grafo; cada nodo agrega su parte. El nodo critico
(patron reflection) revisa la respuesta del especialista: si no cumple la
rubrica, el flujo VUELVE al mismo especialista con el feedback — el primer
ciclo del grafo. En modo demo, los nodos especialistas ejecutan las tools
reales con razonamiento templado y el critico es pass-through (las
plantillas son deterministicas, no hay nada que revisar).
"""
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agents import critic, customs, exceptions, router, tracking
from app.agents.base import run_agent
from app.config import DEMO_MODE
from app.demo_responses import DEMO_HANDLERS

MAX_REVISIONS = 1  # guardrail: una sola vuelta de correccion (costo/latencia acotados)


class CopilotState(TypedDict, total=False):
    message: str
    route: str
    answer: str
    tools_called: list[dict]
    mode: str
    critique: str    # feedback del critico ("" = aprobada)
    revisions: int   # cuantas veces se devolvio la respuesta


SPECIALISTS = {
    "tracking": tracking,
    "exceptions": exceptions,
    "customs": customs,
}


def router_node(state: CopilotState) -> CopilotState:
    if DEMO_MODE:
        return {"route": router.route_by_keywords(state["message"]), "mode": "demo"}
    return {"route": router.route_by_llm(state["message"]), "mode": "live"}


def _make_specialist_node(name: str):
    module = SPECIALISTS[name]

    def node(state: CopilotState) -> CopilotState:
        message = state["message"]
        # Si venimos devueltos por el critico, el agente reintenta CON el feedback
        if state.get("critique"):
            message += (
                "\n\n[REVISION] Tu respuesta anterior fue observada por control de calidad: "
                f"{state['critique']}\nRespuesta anterior:\n{state.get('answer', '')}\n"
                "Corregila."
            )
        if state.get("mode") == "demo":
            answer, tools_called = DEMO_HANDLERS[name](state["message"])
        else:
            answer, tools_called = run_agent(module.SYSTEM_PROMPT, message, module.TOOLS)
        return {
            "answer": answer,
            # se acumulan las tools de todos los intentos (traza completa)
            "tools_called": state.get("tools_called", []) + tools_called,
        }

    return node


def critic_node(state: CopilotState) -> CopilotState:
    revisions = state.get("revisions", 0)
    # Pass-through: en demo no hay LLM que revisar; tras MAX_REVISIONS se entrega igual
    if state.get("mode") == "demo" or revisions >= MAX_REVISIONS:
        return {"critique": ""}
    approved, feedback = critic.review(state["message"], state["route"], state.get("answer", ""))
    if approved:
        return {"critique": ""}
    return {"critique": feedback, "revisions": revisions + 1}


def _route_decision(state: CopilotState) -> str:
    return state["route"]


def _critic_decision(state: CopilotState) -> str:
    # Con feedback pendiente vuelve al especialista que atendio; si no, termina
    return state["route"] if state.get("critique") else END


def build_graph():
    graph = StateGraph(CopilotState)
    graph.add_node("router", router_node)
    graph.add_node("critic", critic_node)
    for name in SPECIALISTS:
        graph.add_node(name, _make_specialist_node(name))
        graph.add_edge(name, "critic")
    graph.set_entry_point("router")
    graph.add_conditional_edges("router", _route_decision, {name: name for name in SPECIALISTS})
    graph.add_conditional_edges("critic", _critic_decision,
                                {**{name: name for name in SPECIALISTS}, END: END})
    return graph.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def ask(message: str) -> dict:
    """Punto de entrada unico del copiloto: corre el grafo completo."""
    result = get_graph().invoke({"message": message})
    return {
        "answer": result["answer"],
        "agent_used": result["route"],
        "tools_called": result.get("tools_called", []),
        "mode": result["mode"],
        "revisions": result.get("revisions", 0),
    }
