# Tour guiado del proyecto (para entender qué construimos)

> Guía para recorrer el sistema pieza por pieza, corriendo cosas de verdad.
> Tiempo estimado: 30-40 minutos. No hace falta API key para nada de esto.

## La historia completa en un párrafo

Este proyecto es un **copiloto de operaciones logísticas**: un operador le pregunta
en lenguaje natural por envíos, problemas o normativa, y un **sistema multiagente**
le responde consultando una base de envíos real (simulada), aplicando un playbook
de decisiones y buscando en documentos de normativa (RAG híbrido). Todo expuesto
como API web y como servidor MCP.

## El viaje de UNA pregunta (leé esto primero)

Pregunta: *"¿qué paquetes están trabados y qué hago?"*

```
1. Entra por la API                      → app/main.py        (endpoint POST /chat)
2. El grafo arranca                      → app/agents/graph.py
3. El ROUTER decide quién atiende        → app/agents/router.py   ("exceptions")
4. El agente de excepciones entra en su
   loop de tool-calling                  → app/agents/base.py
   - pide find_stuck_shipments           → app/tools.py → app/db.py (SQLite)
   - pide classify_exception (x5)        → app/tools.py
   - pide decide_action (x5)             → app/tools.py (playbook, enum cerrado)
5. El LLM redacta el informe final       → app/llm.py (Groq) o app/demo_responses.py
6. La API devuelve respuesta + trazas    → {"answer", "agent_used", "tools_called"}
```

Todo lo demás del repo existe para servir a ese viaje (datos, docs, tests, eval, deploy).

## Parada 1 — Los datos (5 min)

```powershell
python data/seed.py
python -c "from app import db; print(db.count_by_status())"
python -c "from app import db; [print(e['occurred_at'][:10], e['event_code'], e['description']) for e in db.get_events('MA-2026-00022')]"
```

Mirá ese último output: es la "vida" de un paquete, evento por evento. Fijate que
se frenó hace mucho — ese es un envío "stuck". Abrí `data/seed.py` y buscá
`EXCEPTION_TYPES` para ver los 4 tipos de problema que simulamos.

## Parada 2 — Las tools: las manos del sistema (10 min)

Las tools son funciones Python comunes. Probalas directo, sin ningún LLM:

```powershell
python -c "from app import tools; print(tools.classify_exception('MA-2026-00022'))"
python -c "from app import tools; print(tools.decide_action('customs_hold', 80))"
python -c "from app import tools; print(tools.decide_action('customs_hold', 350))"
```

Fijate en las dos últimas: misma excepción, distinto valor → distinta decisión
(la regla "más de USD 200 escala a humano" vive en CÓDIGO, no en un prompt;
el LLM no puede saltearla). Abrí `app/tools.py` y mirá `TOOL_SCHEMAS`: esas
`description` son lo que el LLM lee para decidir qué tool usar.

## Parada 3 — El RAG híbrido (10 min)

```powershell
python eval/compare_retrieval.py
python eval/compare_retrieval.py "se rompio el paquete quien me paga"
```

Tres columnas: `bm25` (palabras), `dense` (significado, necesita GEMINI_API_KEY),
`hybrid` (fusión de ambos). Probá tus propias preguntas y mirá cuándo BM25 le
pifia (parafraseo) y cuándo acierta (códigos exactos). El código: `app/rag.py`
(la fusión RRF son 8 líneas, leelas — es menos mágico de lo que suena).

## Parada 4 — El sistema multiagente completo (10 min)

```powershell
$env:DEMO_MODE='true'
python -c "from app.agents.graph import ask; r = ask('que paquetes estan trabados?'); print('agente:', r['agent_used']); print('tools:', [t['tool'] for t in r['tools_called']]); print(); print(r['answer'])"
```

Mirá `tools` en el output: esa es la SECUENCIA de herramientas que se usó.
Después levantá la API completa y entrá a la documentación interactiva:

```powershell
uvicorn app.main:app
# en el navegador: http://localhost:8000/docs  → probá POST /chat desde ahí
```

## Parada 5 — Tests y eval: la red de seguridad (5 min)

```powershell
python -m pytest tests -q     # ¿el sistema sigue sano? (24 chequeos)
python eval/eval_agent.py     # ¿el routing y las tools aciertan? (10 casos)
```

Diferencia clave (pregunta de entrevista): los **tests** verifican código
determinístico (la DB, el playbook, la API). El **eval** mide la calidad de
las decisiones del sistema agéntico (¿ruteó bien? ¿usó la tool correcta?) —
eso puede degradarse al cambiar de modelo o prompt sin que ningún test falle.

## Parada 6 — La interfaz de chat (5 min)

```powershell
streamlit run ui/app.py
# se abre solo en el navegador: http://localhost:8501
```

Hacé una consulta y fijate: el badge te dice qué agente atendió y en qué modo,
y el desplegable "tools usadas" es la traza del loop — lo mismo que veías en
la terminal, pero visual. El código (`ui/app.py`) es corto: una UI es solo
otra puerta de entrada al mismo `ask()` del grafo.

## Parada 7 — El nodo crítico (reflection) (5 min)

Desde la v2 el grafo tiene un ciclo: cada respuesta pasa por un revisor
(`app/agents/critic.py`) que la chequea contra una rúbrica; si no cumple,
vuelve al agente con feedback (máximo 1 vez). En la UI, si una respuesta fue
corregida vas a ver el badge "🔁 corregida por el crítico". Compará el grafo
nuevo con el viejo:

```powershell
python -c "from app.agents.graph import get_graph; print(get_graph().get_graph().draw_ascii())"
```

## Orden sugerido para LEER el código (de fácil a difícil)

1. `app/db.py` — consultas SQL simples, sin IA
2. `app/tools.py` — funciones + sus descripciones para el LLM
3. `app/agents/tracking.py` — un agente es solo un prompt + lista de tools
4. `app/agents/base.py` — **el corazón: el loop agéntico (30 líneas)**
5. `app/agents/router.py` y `graph.py` — cómo se conectan los agentes
6. `app/rag.py` — búsqueda híbrida BM25 + embeddings + RRF
7. `app/main.py` — la API que envuelve todo
8. `mcp_server/server.py` — las mismas tools por protocolo MCP

## Glosario mínimo

- **LLM**: red neuronal gigante que recibe texto y genera texto. Acá: Llama 3.3 vía Groq.
- **Tool calling**: el LLM pide por escrito que TU código ejecute una función y le devuelva el resultado.
- **Agente**: un LLM en un loop con tools, decidiendo cada paso hasta terminar.
- **Embedding**: lista de números que representa el significado de un texto (acá: 768 números, vía Gemini).
- **BM25**: ranking por coincidencia de palabras (sin IA, local).
- **RAG**: buscar fragmentos relevantes y dárselos al LLM para que responda citando fuentes.
- **RRF**: suma de posiciones en varios rankings para fusionarlos en uno.
- **Guardrail**: límite impuesto por código que el LLM no puede violar (ej: `MAX_ITERATIONS`, escalamiento por valor).
- **Reflection**: un LLM call que revisa la respuesta de otro antes de entregarla, y puede devolverla con feedback (`app/agents/critic.py`).
- **Human-in-the-loop**: pausar el flujo automático para que un humano apruebe antes de seguir (próximo paso del roadmap; el playbook ya escala a humano, pero fuera del grafo).
- **Ciclo (en el grafo)**: una flecha que vuelve a un nodo anterior — lo que diferencia un grafo de una cadena.
