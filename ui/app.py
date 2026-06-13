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

st.set_page_config(
    page_title="Logistics Operations Copilot",
    page_icon="📦",
    layout="centered",
)

EXAMPLES = [
    "¿Dónde está el envío MA-2026-00042?",
    "¿Qué paquetes están trabados y qué hago con cada uno?",
    "¿Cuál es el límite de valor para courier en Argentina?",
]

# ----------------------------------------------------------- estilos

st.markdown(
    """
    <style>
      :root { --accent: #6d5efc; --accent-soft: #efeefe; }
      /* ocultar el chrome de Streamlit -> se ve como un producto, no una app de dev */
      #MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }
      header[data-testid="stHeader"] { background: transparent; height: 0; }
      .block-container { padding-top: 2rem; max-width: 760px; }
      /* header */
      .hero-title { font-size: 1.7rem; font-weight: 700; letter-spacing: -.02em;
                    margin: 0; display: flex; align-items: center; gap: .55rem; }
      .hero-sub { color: #6b7280; font-size: .95rem; margin: .35rem 0 0; line-height: 1.5; }
      /* chat bubbles */
      [data-testid="stChatMessage"] { border-radius: 14px; padding: .35rem .25rem; }
      /* tech chips */
      .chip { display: inline-block; padding: 3px 10px; margin: 3px 4px 3px 0;
              font-size: .72rem; font-weight: 600; border-radius: 999px;
              background: var(--accent-soft); color: var(--accent);
              border: 1px solid #e2e0fb; }
      /* mode pill */
      .pill { display: inline-flex; align-items: center; gap: .4rem; padding: 4px 12px;
              border-radius: 999px; font-size: .78rem; font-weight: 600; }
      .pill-live { background: #e7f7ee; color: #0a8a4a; border: 1px solid #bce8cf; }
      .pill-demo { background: #fff4e5; color: #b4690e; border: 1px solid #f5d9b0; }
      /* botones de ejemplo del sidebar: chips suaves, no cuadrados grises */
      [data-testid="stSidebar"] .stButton button {
          text-align: left; justify-content: flex-start; border-radius: 10px;
          border: 1px solid #ececf6; background: #fbfbfe; color: #4b5563;
          font-size: .8rem; font-weight: 500; padding: .45rem .7rem; line-height: 1.3; }
      [data-testid="stSidebar"] .stButton button:hover {
          border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
      .side-foot { color: #9ca3af; font-size: .76rem; line-height: 1.5; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------- sidebar

with st.sidebar:
    st.markdown("### 📦 Operations Copilot")

    if DEMO_MODE:
        st.markdown('<span class="pill pill-demo">● demo · sin LLM</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="pill pill-live">● live · {MODEL}</span>', unsafe_allow_html=True)

    st.markdown("")
    counts = db.count_by_status()
    st.markdown("##### Operación en vivo")
    c1, c2, c3 = st.columns(3)
    c1.metric("Entregados", counts.get("delivered", 0))
    c2.metric("En tránsito", counts.get("in_transit", 0))
    c3.metric("Excepción", counts.get("exception", 0))

    st.markdown("##### Probá con…")
    for example in EXAMPLES:
        if st.button(example, use_container_width=True):
            st.session_state.pending = example

    st.divider()
    st.markdown(
        '<div class="side-foot">Un router deriva cada consulta a un agente '
        'especialista; las respuestas pasan por un revisor de calidad antes '
        'de entregarse.</div>',
        unsafe_allow_html=True,
    )

# ----------------------------------------------------------- chat header

st.markdown(
    '<p class="hero-title">📦 Logistics Operations Copilot</p>'
    '<p class="hero-sub">Preguntá por envíos, excepciones de entrega o normativa aduanera. '
    'Cada respuesta muestra qué agente la atendió y qué herramientas usó.</p>',
    unsafe_allow_html=True,
)
st.markdown("")


def render_meta(meta: dict) -> None:
    """Badge del agente + traza de tools (transparencia agentica)."""
    chips = f'<span class="chip">🧭 {meta["agent_used"]}</span>'
    chips += f'<span class="chip">{"🧪 demo" if meta["mode"] == "demo" else "🟢 live"}</span>'
    if meta.get("revisions"):
        chips += f'<span class="chip">🔁 corregida ×{meta["revisions"]}</span>'
    st.markdown(chips, unsafe_allow_html=True)
    with st.expander(f"🔧 {len(meta['tools_called'])} herramientas usadas"):
        for t in meta["tools_called"]:
            st.code(f"{t['tool']}({t['args']})", language="python")


if "history" not in st.session_state:
    st.session_state.history = []

for turn in st.session_state.history:
    with st.chat_message(turn["role"], avatar="🧑‍💻" if turn["role"] == "user" else "📦"):
        st.markdown(turn["content"])
        if meta := turn.get("meta"):
            render_meta(meta)

prompt = st.chat_input("Escribí tu consulta…") or st.session_state.pop("pending", None)

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar="📦"):
        try:
            with st.spinner("Los agentes están trabajando…"):
                result = ask(prompt)
            st.markdown(result["answer"])
            render_meta(result)
            st.session_state.history.append(
                {"role": "assistant", "content": result["answer"], "meta": result}
            )
        except Exception:
            msg = ("⚠️ El modelo devolvió una respuesta mal formada en este intento. "
                   "Probá de nuevo o reformulá la consulta.")
            st.warning(msg)
            st.session_state.history.append({"role": "assistant", "content": msg})
