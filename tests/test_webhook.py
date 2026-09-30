"""Pruebas de integración para el Webhook de OpenWA en web/app.py."""

from unittest.mock import AsyncMock, patch
import pytest

from web.app import create_app
from bot import config, db


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test_auditoria.db"
    monkeypatch.setattr(config, "DB_PATH", str(db_file))
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_openwa_webhook_ignores_non_message(client):
    response = client.post("/webhook/openwa", json={"event": "onAck"})
    assert response.status_code == 200
    assert response.get_json() == {"status": "recibido"}


def test_openwa_webhook_ignores_group_message(client):
    payload = {
        "event": "onMessage",
        "data": {
            "from": "123456@g.us",
            "body": "Hola grupo",
            "isGroupMsg": True,
        },
    }
    response = client.post("/webhook/openwa", json=payload)
    assert response.status_code == 200
    assert response.get_json() == {"status": "recibido"}


def test_openwa_webhook_processes_valid_message(client):
    payload = {
        "event": "onMessage",
        "data": {
            "from": "5511999999999@c.us",
            "body": "gasté 50 USD en almuerzo",
            "isGroupMsg": False,
        },
    }

    mock_ai_response = {
        "reply": "Entendido, registré tu gasto.",
        "transactions": [
            {
                "date": "2026-03-30",
                "description": "almuerzo",
                "amount": 50.0,
                "currency": "USD",
                "type": "gasto",
                "category": "restaurantes",
            }
        ],
    }

    with patch("bot.ai.chat", new_callable=AsyncMock) as mock_ai_chat, \
         patch("web.app.enviar_mensaje_wa") as mock_send_wa:

        mock_ai_chat.return_value = mock_ai_response

        response = client.post("/webhook/openwa", json=payload)

        assert response.status_code == 200
        assert response.get_json() == {"status": "recibido"}
        mock_ai_chat.assert_called_once()

        mock_send_wa.assert_called_once()
        chat_id_arg, text_arg = mock_send_wa.call_args[0]
        assert chat_id_arg == "5511999999999@c.us"
        assert "Entendido, registré tu gasto." in text_arg
        assert "• almuerzo: −50.00 USD (restaurantes)" in text_arg
