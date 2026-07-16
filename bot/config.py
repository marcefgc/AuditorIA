"""Configuración central del bot AuditorIA."""

import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DB_PATH = os.environ.get("AUDITORIA_DB_PATH", "auditoria.db")

# Modelo de IA usado para leer documentos y dar consejos
CLAUDE_MODEL = "claude-opus-4-8"

# Cantidad de mensajes de conversación que se conservan como contexto
CHAT_HISTORY_LIMIT = 16


def validate() -> None:
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        raise SystemExit(
            "Faltan variables de entorno: "
            + ", ".join(missing)
            + ". Copia .env.example a .env y completa los valores."
        )
