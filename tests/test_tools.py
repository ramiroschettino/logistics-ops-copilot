from app import tools


def test_get_shipment_unknown():
    assert "error" in tools.get_shipment("MA-2026-99999")


def test_classify_exception_on_stuck_shipment():
    stuck = tools.find_stuck_shipments(min_days_stuck=4, limit=1)["shipments"]
    diag = tools.classify_exception(stuck[0]["tracking_number"])
    assert diag["exception"] in tools.ACTIONS


def test_playbook_actions():
    assert tools._action_for("customs_hold", 50)["action"] == "request_docs"
    assert tools._action_for("invalid_address", 50)["action"] == "notify_buyer"
    assert tools._action_for("carrier_delay", 50)["action"] == "retry_delivery"
    assert tools._action_for("lost_in_transit", 50)["action"] == "mark_lost"


def test_playbook_escalates_high_value():
    """Regla del playbook: valor > USD 200 siempre escala a humano."""
    assert tools._action_for("customs_hold", 350)["action"] == "escalate"


def test_playbook_unknown_exception_escalates():
    assert tools._action_for("alien_abduction", 0)["action"] == "escalate"


def test_decide_action_reads_value_from_db():
    """El valor declarado sale de la DB, no de un argumento del LLM.
    MA-2026-00119 (seed deterministico): lost_in_transit con valor 277.77 > 200."""
    result = tools.decide_action("MA-2026-00119")
    assert result["action"] == "escalate"
    assert result["declared_value_usd"] > 200


def test_decide_action_rejects_llm_supplied_value():
    """Bug real: el LLM paso un valor inventado. La tool ya no acepta ese argumento."""
    result = tools.run_tool("decide_action", {"exception_type": "customs_hold",
                                              "declared_value_usd": 100})
    assert "error" in result


def test_run_tool_dispatch():
    result = tools.run_tool("search_docs", {"query": "sla brasil"})
    assert "results" in result


def test_run_tool_invalid_args():
    assert "error" in tools.run_tool("get_shipment", {"bad_arg": 1})
