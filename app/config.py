"""Configuracion central: lee variables de entorno desde .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL = os.getenv("MODEL", "llama-3.3-70b-versatile")
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "data" / "logistics.db"))
DOCS_DIR = BASE_DIR / "docs"

# Demo mode: las tools corren de verdad (DB + RAG) pero el razonamiento
# del LLM se reemplaza por plantillas deterministicas. Permite demostrar
# la arquitectura sin API key ni internet.
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in ("1", "true", "yes") or not GROQ_API_KEY
