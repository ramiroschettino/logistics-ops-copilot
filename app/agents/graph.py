"""Grafo de orquestacion multiagente (LangGraph).

Topologia: router -> {tracking | exceptions | customs} -> END

El estado fluye por el grafo; cada nodo agrega su parte. En modo demo,
los nodos especialistas ejecutan las tools reales con razonamiento
templado en vez de llamar al LLM (misma topologia, sin API).
"""
from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from app.agents import customs, exceptions, router, tracking
from app.agents.base import run_agent
from app.config import DEMO_MODE
from app.demo_responses import DEMO_HANDLERS


class CopilotState(TypedDict, total=False):
    message: str
    route: str
    answer: str
    tools_called: list[dict]
    mode: str


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
        if state.get("mode") == "demo":
            answer, tools_called = DEMO_HANDLERS[name](state["message"])
        else:
            answer, tools_called = run_agent(module.SYSTEM_PROMPT, state["message"], module.TOOLS)
        return {"answer": answer, "tools_called": tools_called}

    return node


def _route_decision(state: CopilotState) -> Literal["tracking", "exceptions", "customs"]:
    return state["route"]


def build_graph():
    graph = StateGraph(CopilotState)
    graph.add_node("router", router_node)
    for name in SPECIALISTS:
        graph.add_node(name, _make_specialist_node(name))
    graph.set_entry_point("router")
    graph.add_conditional_edges("router", _route_decision, {name: name for name in SPECIALISTS})
    for name in SPECIALISTS:
        graph.add_edge(name, END)
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
    }
