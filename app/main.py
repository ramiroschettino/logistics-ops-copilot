"""API del Logistics Operations Copilot (FastAPI).

Microservicio que expone el sistema multiagente:
- POST /chat            consulta en lenguaje natural -> respuesta + trazas del agente
- GET  /shipments/{tn}  estado de un envio (acceso directo, sin LLM)
- GET  /exceptions      envios atascados con diagnostico y accion decidida
- GET  /health          liveness + modo de operacion
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import db, tools
from app.agents.graph import ask
from app.config import DEMO_MODE, MODEL
from app.rag import get_index


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_index()  # construye el indice BM25 una sola vez al arrancar
    yield


app = FastAPI(
    title="Logistics Operations Copilot",
    description="Sistema multiagente para operaciones de logistica cross-border: "
                "tracking, triage de excepciones y consultas de normativa (RAG).",
    version="1.0.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=2, examples=["Donde esta el envio MA-2026-00042?"])


class ChatResponse(BaseModel):
    answer: str
    agent_used: str
    tools_called: list[dict]
    mode: str
    revisions: int = 0  # veces que el nodo critico devolvio la respuesta


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    return ChatResponse(**ask(req.message))


@app.get("/shipments/{tracking_number}")
def get_shipment(tracking_number: str) -> dict:
    result = tools.get_shipment(tracking_number)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/exceptions")
def list_exceptions(min_days_stuck: int = 4, limit: int = 10) -> dict:
    """Triage automatico: detecta + clasifica + decide para cada envio atascado."""
    stuck = db.find_stuck_shipments(min_days_stuck, limit)
    triage = []
    for s in stuck:
        d = tools.decide_action(s["tracking_number"])
        triage.append({**s, "diagnosis": d.get("exception"),
                       "decision": {"action": d.get("action"), "rationale": d.get("rationale")}})
    return {"count": len(triage), "shipments": triage}


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "mode": "demo" if DEMO_MODE else "live",
        "model": None if DEMO_MODE else MODEL,
        "shipments": db.count_by_status(),
    }
