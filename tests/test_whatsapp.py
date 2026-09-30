"""Pruebas unitarias para el cliente de WhatsApp OpenWA."""

from unittest.mock import MagicMock, patch
import requests

from bot.whatsapp import enviar_mensaje_wa


def test_enviar_mensaje_wa_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "success", "response": True}
    mock_response.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_response) as mock_post:
        res = enviar_mensaje_wa("5511999999999@c.us", "Hola desde AuditorIA")

        assert res == {"status": "success", "response": True}
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0].endswith("/sendText")
        assert kwargs["json"] == {
            "args": {
                "to": "5511999999999@c.us",
                "content": "Hola desde AuditorIA",
            }
        }


def test_enviar_mensaje_wa_error():
    with patch("requests.post", side_effect=requests.exceptions.RequestException("Conn error")):
        res = enviar_mensaje_wa("5511999999999@c.us", "Hola")
        assert res is None
