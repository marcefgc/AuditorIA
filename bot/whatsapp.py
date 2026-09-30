"""Cliente para comunicación con la API REST de OpenWA (Open WhatsApp)."""

import requests
from bot.config import OPENWA_API_URL, OPENWA_SESSION_KEY


def enviar_mensaje_wa(chat_id: str, texto: str) -> dict | None:
    """Envía un mensaje de texto a través de la API de OpenWA."""
    endpoint = f"{OPENWA_API_URL.rstrip('/')}/sendText"
    payload = {
        "args": {
            "to": chat_id,
            "content": texto,
        }
    }
    headers = {}
    if OPENWA_SESSION_KEY:
        headers["Authorization"] = f"Bearer {OPENWA_SESSION_KEY}"

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error al enviar mensaje por OpenWA: {e}")
        return None
