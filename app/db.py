"""Acceso a la base de envios (SQLite, stdlib sin ORM)."""
import sqlite3
from datetime import datetime

from app.config import DB_PATH

# Fecha "actual" del dataset simulado (coincide con data/seed.py)
DATASET_NOW = datetime(2026, 6, 10, 12, 0, 0)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_shipment(tracking_number: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM shipments WHERE tracking_number = ?", (tracking_number.strip().upper(),)
        ).fetchone()
        return dict(row) if row else None


def get_events(tracking_number: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT event_code, description, location, occurred_at FROM events "
            "WHERE tracking_number = ? ORDER BY occurred_at",
            (tracking_number.strip().upper(),),
        ).fetchall()
        return [dict(r) for r in rows]


def find_stuck_shipments(min_days_stuck: int = 4, limit: int = 15) -> list[dict]:
    """Envios no entregados cuyo ultimo evento es mas viejo que `min_days_stuck` dias."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT s.tracking_number, s.destination_country, s.carrier, s.status,
                   s.exception_type, s.declared_value_usd,
                   MAX(e.occurred_at) AS last_event_at,
                   (SELECT e2.description FROM events e2
                    WHERE e2.tracking_number = s.tracking_number
                    ORDER BY e2.occurred_at DESC LIMIT 1) AS last_event
            FROM shipments s JOIN events e ON e.tracking_number = s.tracking_number
            WHERE s.status != 'delivered'
            GROUP BY s.tracking_number
            HAVING julianday(?) - julianday(MAX(e.occurred_at)) >= ?
            ORDER BY last_event_at
            LIMIT ?
            """,
            (DATASET_NOW.isoformat(), min_days_stuck, limit),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["days_stuck"] = round(
                (DATASET_NOW - datetime.fromisoformat(d["last_event_at"])).total_seconds() / 86400, 1
            )
            out.append(d)
        return out


def count_by_status() -> dict:
    with _conn() as conn:
        rows = conn.execute("SELECT status, COUNT(*) AS n FROM shipments GROUP BY status").fetchall()
        return {r["status"]: r["n"] for r in rows}
