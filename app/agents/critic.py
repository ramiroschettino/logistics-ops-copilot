"""Nodo critico (patron 'reflection'): revisa la respuesta antes de entregarla.

Un LLM call extra que actua como control de calidad: si la respuesta no
cumple la rubrica, vuelve al agente especialista CON el feedback para que
la corrija (maximo 1 revision, para acotar costo y latencia). Es el primer
ciclo del grafo: la informacion puede volver hacia atras.

El veredicto se parsea por prefijo de texto plano (APROBADA / REVISAR: ...),
deliberadamente simple: pedir JSON al modelo para un si/no agrega un punto
de falla de parseo sin ganar nada.
"""
from app.llm import get_client

CRITIC_PROMPT = """Sos el revisor de calidad de un copiloto de operaciones logisticas. \
Vas a recibir la CONSULTA del usuario, que AGENTE la atendio y su RESPUESTA.

Rubrica:
1. La respuesta contesta lo que se pregunto (no otra cosa).
2. Si el agente es customs: la respuesta cita la fuente (nombre de archivo).
3. Si el agente es exceptions: la respuesta nombra una accion concreta del playbook.
4. La respuesta no contradice los datos ni inventa cifras.

Si la respuesta cumple, responde exactamente: APROBADA
Si no cumple, responde: REVISAR: <una sola linea diciendo que corregir>
No agregues nada mas."""


def parse_verdict(text: str) -> tuple[bool, str]:
    """Devuelve (aprobada, feedback). Ante veredicto ilegible, aprueba:
    el critico es una mejora de calidad, no un punto de bloqueo."""
    clean = (text or "").strip()
    upper = clean.upper()
    if upper.startswith("APROBADA"):
        return True, ""
    if upper.startswith("REVISAR"):
        _, _, feedback = clean.partition(":")
        return False, feedback.strip() or "Revisar la respuesta."
    return True, ""


def review(question: str, agent: str, answer: str) -> tuple[bool, str]:
    msg = get_client().chat([
        {"role": "system", "content": CRITIC_PROMPT},
        {"role": "user", "content": f"CONSULTA: {question}\nAGENTE: {agent}\nRESPUESTA:\n{answer}"},
    ])
    return parse_verdict(msg.content)
