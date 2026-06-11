"""Cliente LLM agnostico al proveedor.

Hoy usa Groq (API OpenAI-compatible, free tier). Cambiar de proveedor =
cambiar esta clase, los agentes no se enteran. Si no hay API key o
DEMO_MODE=true, el grafo no llama al LLM (ver agents/graph.py).
"""
from groq import Groq

from app.config import GROQ_API_KEY, MODEL


class LLMClient:
    def __init__(self, api_key: str = GROQ_API_KEY, model: str = MODEL):
        self.model = model
        self._client = Groq(api_key=api_key) if api_key else None

    @property
    def available(self) -> bool:
        return self._client is not None

    def chat(self, messages: list[dict], tools: list[dict] | None = None, temperature: float = 0.1):
        """Una vuelta de chat completion. Devuelve el message del modelo
        (puede traer tool_calls que el agente debe ejecutar)."""
        kwargs = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message


_client: LLMClient | None = None


def get_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
