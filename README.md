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
   Usuario / Claude Desktop (MCP) / curl
                  │
                  ▼
   ┌─────────────────────────────────┐
   │  FastAPI  /chat /shipments      │   ← microservicio
   │           /exceptions /health   │
   └───────────────┬─────────────────┘
                   ▼
   ┌─────────────────────────────────┐
   │   Router Agent  (LangGraph)     │   ← clasifica y deriva
   └───┬───────────┬───────────┬─────┘
       ▼           ▼           ▼
  ┌─────────┐ ┌──────────┐ ┌─────────┐
  │Tracking │ │Exceptions│ │ Customs │   ← agentes especialistas
  │ Agent   │ │  Agent   │ │  (RAG)  │      con tool-calling loop
  └────┬────┘ └────┬─────┘ └────┬────┘
       ▼           ▼            ▼
   SQLite      playbook +    BM25 sobre
   (envíos)    decisión      docs/ (normativa
               por enum      aduanera, SLAs)
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
- **RAG con BM25** (puro Python) en vez de embeddings densos: corre en cualquier
  máquina sin GPU, sin descargar modelos. Chunking por sección de markdown, citas
  de fuente en cada respuesta. (Upgrade natural: híbrido BM25 + denso con reranker.)
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

- Retrieval híbrido (BM25 + embeddings) con reranking y eval de retrieval (recall@k).
- Observabilidad de agentes: trazas con Langfuse/OpenTelemetry, costo por consulta.
- Memoria de conversación multi-turno (checkpointer de LangGraph).
- Agente proactivo programado (cron) que corre el triage y notifica por Slack/email.
- Deploy real: Cloud Run / ECS con secretos gestionados y autoscaling.
