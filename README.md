# Logistics Operations Copilot

Sistema **multiagente** para operaciones de logística cross-border de e-commerce:
tracking de envíos, **triage autónomo de excepciones de entrega** y consultas de
normativa aduanera con **RAG**. Expuesto como **microservicio FastAPI** y como
**servidor MCP** (Model Context Protocol).

> Caso de uso inspirado en la operación de un consolidador postal que mueve paquetes
> desde China/USA/Europa hacia última milla en LatAm: detectar envíos atascados
> (aduana, dirección inválida, demora de carrier), diagnosticar la causa y **decidir
> la acción operativa** según un playbook — sin intervención humana salvo escalamiento.

## Arquitectura

```
   UI chat (Streamlit) / Claude Desktop (MCP) / curl
                  │
                  ▼
   ┌─────────────────────────────────┐
   │  FastAPI  /chat /shipments      │   ← microservicio
   │           /exceptions /health   │
   └───────────────┬─────────────────┘
                   ▼
   ┌─────────────────────────────────┐
   │   Router  (LangGraph)           │   ← clasifica y deriva
   └───┬───────────┬───────────┬─────┘
       ▼           ▼           ▼
  ┌─────────┐ ┌──────────┐ ┌─────────┐
  │Tracking │ │Exceptions│ │ Customs │   ← agentes especialistas
  │ Agent   │ │  Agent   │ │  (RAG)  │      con tool-calling loop
  └────┬────┘ └────┬─────┘ └────┬────┘
       │           │            │
   SQLite      playbook +    búsqueda híbrida
   (envíos)    decisión      BM25 + embeddings
               por enum      (fusión RRF)
       └───────────┼────────────┘
                   ▼
   ┌─────────────────────────────────┐
   │  Critic (reflection)            │   ← revisa contra rúbrica;
   │  APROBADA → fin                 │     si no cumple, devuelve al
   │  REVISAR → vuelve al agente ↺   │     agente con feedback (máx 1)
   └─────────────────────────────────┘
                   │
                   ▼
        Groq API (Llama 3.3 70B)  ó  DEMO_MODE (offline)
```

**Decisiones de diseño:**

- **Router → especialistas** en vez de un agente monolítico: cada agente tiene un
  system prompt corto y un subset de tools → menos alucinación, más fácil de evaluar.
- **La decisión operativa es un enum cerrado** (`request_docs | notify_buyer |
  retry_delivery | mark_lost | escalate`) implementado en código, no en el prompt.
  El LLM decide *cuándo* invocarla; el código garantiza *qué* hace. Decisiones
  auditables, regla de escalamiento por valor (> USD 200 → humano) inviolable.
- **RAG híbrido** (`app/rag.py`): BM25 (léxico, imbatible con tracking numbers y
  códigos) + embeddings de Gemini (semántico, free tier, con caché en disco),
  fusionados con Reciprocal Rank Fusion. Sin GEMINI_API_KEY degrada solo a BM25
  (graceful degradation). Chunking por sección de markdown, citas de fuente.
- **Datos críticos viajan por código, no por el LLM**: `decide_action` recibe solo
  el tracking y lee el valor declarado de la DB. Motivo: en una corrida real el
  modelo pasó un valor inventado que podía saltear el guardrail de escalamiento.
- **Nodo crítico (reflection)**: un LLM call revisa cada respuesta contra una
  rúbrica antes de entregarla; si no cumple, vuelve al agente con feedback (máx
  1 ciclo). Veredicto por prefijo de texto plano — sin parseo JSON frágil.
- **Cliente LLM agnóstico al proveedor** (`app/llm.py`): cambiar Groq por
  Anthropic/OpenAI/vLLM toca un solo archivo.
- **`DEMO_MODE`**: sin API key, las tools corren igual (DB + RAG reales) y el
  razonamiento se reemplaza por plantillas → la demo funciona offline.

## Quick start

```bash
pip install -r requirements.txt
python data/seed.py                 # genera 200 envíos simulados (24 con excepciones)
copy .env.example .env              # poner GROQ_API_KEY (gratis en console.groq.com)
uvicorn app.main:app --reload
```

Abrir `http://localhost:8000/docs` (Swagger autogenerado) o por curl:

```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d "{\"message\": \"¿Qué paquetes están trabados y qué hago con cada uno?\"}"
```

Respuesta (nota la **transparencia agéntica**: qué agente atendió y qué tools usó):

```json
{
  "answer": "- MA-2026-00119 (BR, USD 277.77): lost_in_transit hace 58.7 días -> ACCION: escalate ...",
  "agent_used": "exceptions",
  "tools_called": [{"tool": "find_stuck_shipments", "args": {}}, {"tool": "classify_exception", "..."}],
  "mode": "live"
}
```

Endpoints sin LLM (integración directa): `GET /shipments/{tracking}`,
`GET /exceptions` (triage batch de toda la operación), `GET /health`.

## UI de chat

```bash
streamlit run ui/app.py    # http://localhost:8501
```

Chat con métricas de la operación en vivo, badge del agente que atendió cada
respuesta y traza expandible de tools usadas (transparencia agéntica, visual).

## Servidor MCP

Las mismas tools expuestas por protocolo estándar para cualquier cliente MCP
(p. ej. Claude Desktop). Agregar a `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "logistics-copilot": {
      "command": "python",
      "args": ["C:/Proyectos/Mailamericas/mcp_server/server.py"]
    }
  }
}
```

Tools MCP: `get_shipment`, `list_stuck_shipments`, `triage_shipment`, `search_customs_docs`.

## Tests y evaluación

```bash
python -m pytest tests -q       # 24 tests (DB, RAG, tools, API) — corren sin API key
python eval/eval_agent.py       # eval-set de 10 consultas: routing y tool accuracy
```

La eval mide **routing accuracy** (¿la consulta llegó al agente correcto?) y
**tool accuracy** (¿se invocó la tool esperada?) — métricas estables que no dependen
de la redacción del LLM. Permite comparar modelos/prompts sin eval subjetiva.
CI en GitHub Actions corre tests + eval en cada push (`.github/workflows/ci.yml`).

## Despliegue

```bash
docker compose up --build       # imagen python:3.12-slim con healthcheck
```

## Mapeo con un rol de AI Engineer

| Requisito | Dónde está en este repo |
|---|---|
| Flujos agénticos / multiagente | `app/agents/graph.py` (LangGraph: router + 3 especialistas) |
| Toma de decisiones autónoma | `app/tools.py::decide_action` + agente de excepciones |
| RAG | `app/rag.py` + `docs/` (BM25, chunking por sección, citas) |
| MCP | `mcp_server/server.py` (SDK oficial, stdio) |
| LLMs / tool use | `app/agents/base.py` (loop de tool-calling con guardrail) |
| APIs y microservicios | `app/main.py` (FastAPI, validación Pydantic, OpenAPI) |
| MLOps / CI/CD | `tests/`, `eval/`, `.github/workflows/ci.yml`, `Dockerfile` |
| Eficiencia de costos | Groq free tier, BM25 sin GPU, modelo intercambiable |

## Next steps (roadmap)

- ~~Retrieval híbrido (BM25 + embeddings)~~ ✅ hecho (`app/rag.py` + `eval/compare_retrieval.py`)
- ~~UI de chat~~ ✅ hecho (`ui/app.py`)
- ~~Reflection / control de calidad~~ ✅ hecho (`app/agents/critic.py`)
- Reranking con cross-encoder y eval de retrieval (recall@k).
- Observabilidad de agentes: trazas con Langfuse/OpenTelemetry, costo por consulta.
- Memoria de conversación multi-turno + human-in-the-loop (checkpointer de LangGraph).
- Agente proactivo programado (cron) que corre el triage y notifica por Slack/email.
- Deploy real: Cloud Run / ECS con secretos gestionados y autoscaling.
