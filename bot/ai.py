"""Integración con la API de Claude: lectura de documentos y asesoría."""

import base64
import json

import anthropic

from . import config, prompts

client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

CATEGORIES = [
    "alimentacion",
    "restaurantes",
    "transporte",
    "vivienda",
    "servicios",
    "suscripciones",
    "salud",
    "educacion",
    "entretenimiento",
    "ropa",
    "viajes",
    "deudas",
    "ahorro",
    "transferencias",
    "otros",
]

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "is_financial_document": {
            "type": "boolean",
            "description": "false si la imagen no es un documento financiero",
        },
        "document_type": {
            "type": "string",
            "enum": [
                "factura",
                "ticket",
                "recibo",
                "transferencia",
                "extracto_tarjeta",
                "extracto_bancario",
                "captura_transaccion",
                "otro",
            ],
        },
        "merchant": {
            "type": ["string", "null"],
            "description": "Comercio, banco o emisor del documento",
        },
        "transactions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
                    "description": {"type": "string"},
                    "amount": {"type": "number", "description": "Monto positivo"},
                    "currency": {"type": "string", "description": "Código ISO 4217"},
                    "type": {"type": "string", "enum": ["gasto", "ingreso"]},
                    "category": {"type": "string", "enum": CATEGORIES},
                },
                "required": [
                    "date",
                    "description",
                    "amount",
                    "currency",
                    "type",
                    "category",
                ],
                "additionalProperties": False,
            },
        },
        "notes": {"type": ["string", "null"]},
    },
    "required": [
        "is_financial_document",
        "document_type",
        "merchant",
        "transactions",
        "notes",
    ],
    "additionalProperties": False,
}


class RefusalError(Exception):
    """La IA declinó procesar la solicitud."""


def _first_text(response) -> str:
    if response.stop_reason == "refusal":
        raise RefusalError("La solicitud fue rechazada por políticas de seguridad.")
    return next(b.text for b in response.content if b.type == "text")


async def extract_document(data: bytes, mime_type: str) -> dict:
    """Lee una foto/PDF de un documento financiero y devuelve datos estructurados."""
    encoded = base64.standard_b64encode(data).decode("utf-8")
    if mime_type == "application/pdf":
        media_block = {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": encoded,
            },
        }
    else:
        media_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": mime_type, "data": encoded},
        }

    response = await client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=prompts.EXTRACTION_SYSTEM,
        output_config={
            "format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA}
        },
        messages=[
            {
                "role": "user",
                "content": [
                    media_block,
                    {"type": "text", "text": prompts.EXTRACTION_USER_PROMPT},
                ],
            }
        ],
    )
    return json.loads(_first_text(response))


async def advise(history: list[dict], user_message: str, snapshot: str) -> str:
    """Responde como asesor financiero usando el historial y los datos del usuario."""
    content = (
        f"<contexto_financiero>\n{snapshot}\n</contexto_financiero>\n\n{user_message}"
    )
    messages = history + [{"role": "user", "content": content}]

    response = await client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": prompts.ADVISOR_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
    )
    return _first_text(response)
