"""Configuración central del bot AuditorIA."""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    # Sin python-dotenv se usan las variables de entorno del sistema;
    # _check_dependencies() avisará que falta el paquete.
    pass

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
DB_PATH = os.environ.get("AUDITORIA_DB_PATH", "auditoria.db")

# ----------------------------------------------------------------- proveedor IA
# AI_PROVIDER:
#   "anthropic" -> API de Anthropic (Claude)
#   "openai"    -> cualquier API compatible con OpenAI (OpenAI, Gemini, Groq,
#                  DeepSeek, Mistral, OpenRouter, Ollama, etc.) usando
#                  AI_BASE_URL para apuntar al endpoint del proveedor.
AI_PROVIDER = os.environ.get("AI_PROVIDER", "anthropic").strip().lower()

_DEFAULT_MODELS = {
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o",
}

AI_MODEL = os.environ.get("AI_MODEL", "") or _DEFAULT_MODELS.get(AI_PROVIDER, "")

# Endpoint personalizado (solo proveedores compatibles con OpenAI).
# Ej.: https://generativelanguage.googleapis.com/v1beta/openai/  (Gemini)
#      https://api.groq.com/openai/v1                            (Groq)
#      http://localhost:11434/v1                                 (Ollama)
AI_BASE_URL = os.environ.get("AI_BASE_URL", "").strip()

# Clave del proveedor. Si no se define, se usa ANTHROPIC_API_KEY u
# OPENAI_API_KEY según el proveedor elegido.
AI_API_KEY = (
    os.environ.get("AI_API_KEY", "")
    or (
        os.environ.get("ANTHROPIC_API_KEY", "")
        if AI_PROVIDER == "anthropic"
        else os.environ.get("OPENAI_API_KEY", "")
    )
)

# Cantidad de mensajes de conversación que se conservan como contexto
CHAT_HISTORY_LIMIT = 16


def _check_dependencies() -> None:
    """Falla al arrancar (y no a mitad de uso) si faltan paquetes."""
    import importlib.util

    required = {
        "telegram": "python-telegram-bot",
        "dotenv": "python-dotenv",
        "PIL": "pillow",
        "pypdfium2": "pypdfium2",
        "anthropic" if AI_PROVIDER == "anthropic" else "openai": (
            "anthropic" if AI_PROVIDER == "anthropic" else "openai"
        ),
    }
    missing = [pkg for mod, pkg in required.items() if importlib.util.find_spec(mod) is None]
    if missing:
        raise SystemExit(
            "Faltan paquetes de Python: "
            + ", ".join(missing)
            + ".\nInstálalos con:  pip install -r requirements.txt"
        )


def validate() -> None:
    _check_dependencies()
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if AI_PROVIDER not in ("anthropic", "openai"):
        raise SystemExit(
            f"AI_PROVIDER inválido: {AI_PROVIDER!r}. "
            "Usa 'anthropic' o 'openai' (compatible con OpenAI)."
        )
    if not AI_API_KEY:
        missing.append(
            "AI_API_KEY (o ANTHROPIC_API_KEY / OPENAI_API_KEY según el proveedor)"
        )
    if not AI_MODEL:
        missing.append("AI_MODEL")
    if missing:
        raise SystemExit(
            "Faltan variables de entorno: "
            + ", ".join(missing)
            + ". Copia .env.example a .env y completa los valores."
        )
