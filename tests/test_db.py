from app import db


def test_dataset_seeded():
    counts = db.count_by_status()
    assert sum(counts.values()) == 200
    assert counts["exception"] == 24


def test_get_shipment_normalizes_input():
    ship = db.get_shipment("  ma-2026-00001  ")
    assert ship is not None
    assert ship["tracking_number"] == "MA-2026-00001"


def test_get_shipment_not_found():
    assert db.get_shipment("MA-2026-99999") is None


def test_events_are_ordered():
    events = db.get_events("MA-2026-00001")
    assert len(events) >= 1
    timestamps = [e["occurred_at"] for e in events]
    assert timestamps == sorted(timestamps)


def test_stuck_shipments_have_min_days():
    stuck = db.find_stuck_shipments(min_days_stuck=4, limit=50)
    assert len(stuck) > 0
    assert all(s["days_stuck"] >= 4 for s in stuck)
    assert all(s["status"] != "delivered" for s in stuck)
