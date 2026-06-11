"""Loop de tool-calling compartido por los agentes especialistas.

Patron clasico de agente: el LLM decide que tool invocar, el codigo la
ejecuta y le devuelve el resultado, hasta que el LLM responde en texto
o se agota el limite de iteraciones (guardrail anti-loop).
"""
import json

from app.llm import get_client
from app.tools import TOOL_SCHEMAS, run_tool

MAX_ITERATIONS = 5


def run_agent(system_prompt: str, user_message: str, tool_names: list[str]) -> tuple[str, list[dict]]:
    """Devuelve (respuesta_final, tools_invocadas)."""
    llm = get_client()
    tools = [TOOL_SCHEMAS[name] for name in tool_names]
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    tools_called: list[dict] = []

    for _ in range(MAX_ITERATIONS):
        msg = llm.chat(messages, tools=tools)
        if not msg.tool_calls:
            return msg.content or "", tools_called

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            result = run_tool(tc.function.name, args)
            tools_called.append({"tool": tc.function.name, "args": args})
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    return "No pude resolver la consulta dentro del limite de pasos del agente.", tools_called
