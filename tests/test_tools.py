from app import tools


def test_get_shipment_unknown():
    assert "error" in tools.get_shipment("MA-2026-99999")


def test_classify_exception_on_stuck_shipment():
    stuck = tools.find_stuck_shipments(min_days_stuck=4, limit=1)["shipments"]
    diag = tools.classify_exception(stuck[0]["tracking_number"])
    assert diag["exception"] in tools.ACTIONS


def test_decide_action_follows_playbook():
    assert tools.decide_action("customs_hold", 50)["action"] == "request_docs"
    assert tools.decide_action("invalid_address", 50)["action"] == "notify_buyer"
    assert tools.decide_action("carrier_delay", 50)["action"] == "retry_delivery"
    assert tools.decide_action("lost_in_transit", 50)["action"] == "mark_lost"


def test_decide_action_escalates_high_value():
    """Regla del playbook: valor > USD 200 siempre escala a humano."""
    assert tools.decide_action("customs_hold", 350)["action"] == "escalate"


def test_decide_action_unknown_exception_escalates():
    assert tools.decide_action("alien_abduction")["action"] == "escalate"


def test_run_tool_dispatch():
    result = tools.run_tool("search_docs", {"query": "sla brasil"})
    assert "results" in result


def test_run_tool_invalid_args():
    assert "error" in tools.run_tool("get_shipment", {"bad_arg": 1})
