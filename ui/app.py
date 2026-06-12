"""UI de chat del Logistics Operations Copilot (Streamlit).

Interfaz visual para demos y para usuarios de negocio. Llama al grafo
directamente (mismo proceso); los sistemas externos siguen integrandose
por la API FastAPI o el servidor MCP.

Correr: streamlit run ui/app.py
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402
from app.agents.graph import ask  # noqa: E402
from app.config import DEMO_MODE, MODEL  # noqa: E402

st.set_page_config(page_title="Logistics Operations Copilot", page_icon="🚚", layout="centered")

EXAMPLES = [
    "¿Dónde está el envío MA-2026-00042?",
    "¿Qué paquetes están trabados y qué hago con cada uno?",
    "¿Cuál es el límite de valor para courier en Argentina?",
]

# ----------------------------------------------------------- sidebar

with st.sidebar:
    st.title("🚚 Copilot")
    mode = "🧪 demo (sin LLM)" if DEMO_MODE else f"🟢 live · {MODEL}"
    st.caption(f"Modo: {mode}")

    counts = db.count_by_status()
    st.subheader("Operación")
    c1, c2, c3 = st.columns(3)
    c1.metric("Entregados", counts.get("delivered", 0))
    c2.metric("En tránsito", counts.get("in_transit", 0))
    c3.metric("Excepción", counts.get("exception", 0))

    st.subheader("Probá con...")
    for example in EXAMPLES:
        if st.button(example, use_container_width=True):
            st.session_state.pending = example

    st.divider()
    st.caption("Multiagente (LangGraph) · RAG híbrido · nodo crítico · "
               "[código](https://github.com)")

# ----------------------------------------------------------- chat

st.title("Logistics Operations Copilot")
st.caption("Preguntame por envíos, excepciones de entrega o normativa aduanera.")

if "history" not in st.session_state:
    st.session_state.history = []

for turn in st.session_state.history:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])
        if meta := turn.get("meta"):
            badge = f"`agente: {meta['agent_used']}` · `modo: {meta['mode']}`"
            if meta.get("revisions"):
                badge += f" · `🔁 corregida por el crítico x{meta['revisions']}`"
            st.caption(badge)
            with st.expander(f"🔧 {len(meta['tools_called'])} tools usadas"):
                for t in meta["tools_called"]:
                    st.code(f"{t['tool']}({t['args']})", language=None)

prompt = st.chat_input("Escribí tu consulta...") or st.session_state.pop("pending", None)

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Los agentes están trabajando..."):
            result = ask(prompt)
        st.markdown(result["answer"])
        badge = f"`agente: {result['agent_used']}` · `modo: {result['mode']}`"
        if result.get("revisions"):
            badge += f" · `🔁 corregida por el crítico x{result['revisions']}`"
        st.caption(badge)
        with st.expander(f"🔧 {len(result['tools_called'])} tools usadas"):
            for t in result["tools_called"]:
                st.code(f"{t['tool']}({t['args']})", language=None)
    st.session_state.history.append(
        {"role": "assistant", "content": result["answer"], "meta": result}
    )
