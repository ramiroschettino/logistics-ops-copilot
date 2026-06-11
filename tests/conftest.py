"""Config de tests: fuerza modo demo (sin API key) y garantiza la DB seedeada."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["DEMO_MODE"] = "true"  # antes de importar app.config

from app.config import DB_PATH  # noqa: E402

if not DB_PATH.exists():
    from data.seed import seed
    seed()
