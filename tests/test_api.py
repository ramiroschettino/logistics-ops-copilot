from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mode"] == "demo"


def test_chat_routes_to_tracking():
    r = client.post("/chat", json={"message": "Donde esta el envio MA-2026-00001?"})
    assert r.status_code == 200
    body = r.json()
    assert body["agent_used"] == "tracking"
    assert any(t["tool"] == "get_shipment" for t in body["tools_called"])


def test_chat_routes_to_exceptions():
    r = client.post("/chat", json={"message": "Que paquetes estan trabados y que hago?"})
    body = r.json()
    assert body["agent_used"] == "exceptions"
    assert any(t["tool"] == "decide_action" for t in body["tools_called"])


def test_chat_routes_to_customs():
    r = client.post("/chat", json={"message": "Cual es la franquicia de impuestos en Mexico?"})
    body = r.json()
    assert body["agent_used"] == "customs"
    assert any(t["tool"] == "search_docs" for t in body["tools_called"])


def test_shipment_endpoint():
    r = client.get("/shipments/MA-2026-00001")
    assert r.status_code == 200
    assert r.json()["shipment"]["tracking_number"] == "MA-2026-00001"


def test_shipment_404():
    assert client.get("/shipments/MA-2026-99999").status_code == 404


def test_exceptions_endpoint_triage():
    r = client.get("/exceptions")
    body = r.json()
    assert body["count"] > 0
    first = body["shipments"][0]
    assert "decision" in first and "action" in first["decision"]


def test_chat_validates_input():
    assert client.post("/chat", json={"message": ""}).status_code == 422
