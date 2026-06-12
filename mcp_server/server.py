"""Servidor MCP (Model Context Protocol) del Logistics Operations Copilot.

Expone las tools de logistica por el protocolo estandar, de modo que
cualquier cliente MCP (Claude Desktop, IDEs, otros agentes) pueda usarlas
sin integrarse con nuestra API. Transporte: stdio.

Configuracion para Claude Desktop (claude_desktop_config.json):
{
  "mcpServers": {
    "logistics-copilot": {
      "command": "python",
      "args": ["C:/Proyectos/Mailamericas/mcp_server/server.py"]
    }
  }
}
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from app import tools  # noqa: E402

mcp = FastMCP("logistics-copilot")


@mcp.tool()
def get_shipment(tracking_number: str) -> dict:
    """Estado actual e historial de eventos de un envio cross-border (formato MA-2026-XXXXX)."""
    return tools.get_shipment(tracking_number)


@mcp.tool()
def list_stuck_shipments(min_days_stuck: int = 4, limit: int = 10) -> dict:
    """Envios atascados: sin eventos nuevos hace `min_days_stuck` dias o mas."""
    return tools.find_stuck_shipments(min_days_stuck, limit)


@mcp.tool()
def triage_shipment(tracking_number: str) -> dict:
    """Diagnostica la excepcion de un envio y decide la accion operativa segun el playbook."""
    return tools.decide_action(tracking_number)


@mcp.tool()
def search_customs_docs(query: str, k: int = 3) -> dict:
    """Busca en la base de conocimiento: normativa aduanera AR/BR/MX, SLAs y playbook de excepciones."""
    return tools.search_docs(query, k)


if __name__ == "__main__":
    mcp.run()  # stdio por defecto
