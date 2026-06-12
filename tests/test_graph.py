"""Tests del grafo y del nodo critico (corren offline, en modo demo)."""
from app.agents.critic import parse_verdict
from app.agents.graph import ask


def test_parse_verdict_approved():
    assert parse_verdict("APROBADA") == (True, "")
    assert parse_verdict("  aprobada  ") == (True, "")


def test_parse_verdict_revise():
    ok, feedback = parse_verdict("REVISAR: falta citar la fuente")
    assert not ok
    assert feedback == "falta citar la fuente"


def test_parse_verdict_garbage_approves():
    """Veredicto ilegible -> aprobar: el critico mejora calidad, no bloquea."""
    assert parse_verdict("el modelo dijo cualquier cosa")[0] is True
    assert parse_verdict("")[0] is True


def test_graph_demo_passes_critic_without_revision():
    result = ask("donde esta el envio MA-2026-00001?")
    assert result["revisions"] == 0
    assert result["agent_used"] == "tracking"
    assert "revisions" in result
