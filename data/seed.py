"""Genera la base SQLite con envios cross-border simulados.

~200 envios China/USA/EU -> LatAm con historial de eventos estilo postal.
Una porcion queda "atascada" (sin eventos hace varios dias) para que el
agente de excepciones tenga casos reales que detectar y triagear.

Uso: python data/seed.py
"""
import random
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import DB_PATH  # noqa: E402

random.seed(42)

ORIGINS = ["CN", "US", "ES", "DE", "GB"]
DESTINATIONS = ["AR", "BR", "MX", "CL", "CO", "PE"]
CARRIERS = ["Correo Argentino", "Correios BR", "Estafeta", "Chilexpress", "Servientrega", "Serpost"]
SERVICES = ["standard", "registered", "express"]
DEST_CARRIER = {
    "AR": "Correo Argentino", "BR": "Correios BR", "MX": "Estafeta",
    "CL": "Chilexpress", "CO": "Servientrega", "PE": "Serpost",
}

# Codigos de evento estilo UPU/postal
EVENTS_HAPPY = [
    ("EMA", "Admitido en origen"),
    ("EMB", "Salida de oficina de cambio de origen"),
    ("EMC", "Llegada a oficina de cambio de destino"),
    ("EDA", "Ingreso a aduana"),
    ("EDC", "Liberado de aduana"),
    ("EMD", "En centro de distribucion"),
    ("EME", "En reparto - ultima milla"),
    ("EMI", "Entregado"),
]

EXCEPTION_TYPES = {
    "customs_hold": ("EDB", "Retenido en aduana - documentacion requerida"),
    "invalid_address": ("EMH", "Intento de entrega fallido - direccion invalida"),
    "carrier_delay": ("EMD", "En centro de distribucion"),  # se queda frenado aca
    "lost_in_transit": ("EMB", "Salida de oficina de cambio de origen"),  # nunca llego
}

CITIES = {
    "CN": "Shenzhen", "US": "Miami", "ES": "Madrid", "DE": "Frankfurt", "GB": "Londres",
    "AR": "Buenos Aires", "BR": "Curitiba", "MX": "CDMX", "CL": "Santiago",
    "CO": "Bogota", "PE": "Lima",
}

NOW = datetime(2026, 6, 10, 12, 0, 0)


def build_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    DROP TABLE IF EXISTS events;
    DROP TABLE IF EXISTS shipments;
    CREATE TABLE shipments (
        tracking_number TEXT PRIMARY KEY,
        origin_country TEXT NOT NULL,
        destination_country TEXT NOT NULL,
        carrier TEXT NOT NULL,
        service_level TEXT NOT NULL,
        declared_value_usd REAL NOT NULL,
        weight_kg REAL NOT NULL,
        status TEXT NOT NULL,
        exception_type TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tracking_number TEXT NOT NULL REFERENCES shipments(tracking_number),
        event_code TEXT NOT NULL,
        description TEXT NOT NULL,
        location TEXT NOT NULL,
        occurred_at TEXT NOT NULL
    );
    CREATE INDEX idx_events_tracking ON events(tracking_number);
    """)


def make_shipment(i: int) -> dict:
    origin = random.choice(ORIGINS)
    dest = random.choice(DESTINATIONS)
    created = NOW - timedelta(days=random.randint(2, 60), hours=random.randint(0, 23))
    return {
        "tracking_number": f"MA-2026-{i:05d}",
        "origin_country": origin,
        "destination_country": dest,
        "carrier": DEST_CARRIER[dest],
        "service_level": random.choice(SERVICES),
        "declared_value_usd": round(random.uniform(5, 380), 2),
        "weight_kg": round(random.uniform(0.1, 4.5), 2),
        "created_at": created.isoformat(),
        "_created": created,
    }


def event_location(code: str, ship: dict) -> str:
    if code in ("EMA", "EMB"):
        return CITIES[ship["origin_country"]]
    return CITIES[ship["destination_country"]]


def seed() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    build_schema(conn)

    n_total, n_exceptions = 200, 24
    exception_ids = set(random.sample(range(1, n_total + 1), n_exceptions))
    counts = {"delivered": 0, "in_transit": 0, "exception": 0}

    for i in range(1, n_total + 1):
        ship = make_shipment(i)
        events = []
        t = ship["_created"]

        if i in exception_ids:
            exc_type = random.choice(list(EXCEPTION_TYPES))
            # avanza por el happy path hasta el punto de falla
            cut = {"customs_hold": 4, "invalid_address": 7, "carrier_delay": 6, "lost_in_transit": 2}[exc_type]
            for code, desc in EVENTS_HAPPY[:cut]:
                events.append((code, desc, event_location(code, ship), t))
                t += timedelta(hours=random.randint(8, 48))
            code, desc = EXCEPTION_TYPES[exc_type]
            # el ultimo evento quedo hace 4-15 dias -> envio "stuck"
            stuck_at = NOW - timedelta(days=random.randint(4, 15))
            events.append((code, desc, event_location(code, ship), max(t, stuck_at)))
            status, exception_type = "exception", exc_type
            counts["exception"] += 1
        else:
            delivered = random.random() < 0.62
            n_steps = len(EVENTS_HAPPY) if delivered else random.randint(2, 6)
            for code, desc in EVENTS_HAPPY[:n_steps]:
                if t > NOW:
                    break
                events.append((code, desc, event_location(code, ship), t))
                t += timedelta(hours=random.randint(6, 36))
            status = "delivered" if events and events[-1][0] == "EMI" else "in_transit"
            exception_type = None
            counts[status] += 1

        conn.execute(
            "INSERT INTO shipments VALUES (?,?,?,?,?,?,?,?,?,?)",
            (ship["tracking_number"], ship["origin_country"], ship["destination_country"],
             ship["carrier"], ship["service_level"], ship["declared_value_usd"],
             ship["weight_kg"], status, exception_type, ship["created_at"]),
        )
        conn.executemany(
            "INSERT INTO events (tracking_number, event_code, description, location, occurred_at) "
            "VALUES (?,?,?,?,?)",
            [(ship["tracking_number"], c, d, loc, ts.isoformat()) for c, d, loc, ts in events],
        )

    conn.commit()
    conn.close()
    print(f"OK -> {DB_PATH}")
    print(f"  envios: {n_total} | entregados: {counts['delivered']} | "
          f"en transito: {counts['in_transit']} | con excepcion: {counts['exception']}")


if __name__ == "__main__":
    seed()
