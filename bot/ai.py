"""Capa de IA con proveedores intercambiables.

Soporta dos backends configurables vía variables de entorno (ver config.py):

- ``anthropic``: API de Anthropic (Claude), con salidas estructuradas nativas.
- ``openai``: cualquier API compatible con OpenAI — OpenAI, Gemini, Groq,
  DeepSeek, Mistral, OpenRouter, Ollama, etc. — apuntando ``AI_BASE_URL`` al
  endpoint del proveedor.

Ambos exponen la misma interfaz: ``extract_document()`` y ``advise()``.
"""

import base64
import io
import json
import re

from . import config, prompts

# Máximo de páginas de un PDF que se envían al modelo (convertidas a imagen)
MAX_PDF_PAGES = 8

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


def _pdf_to_images(data: bytes, max_pages: int = MAX_PDF_PAGES) -> list[bytes]:
    """Convierte las páginas de un PDF en imágenes PNG.

    Permite leer PDFs con cualquier proveedor de visión, incluso los que no
    aceptan PDFs de forma nativa. La conversión ocurre localmente.
    """
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        images = []
        for i in range(min(len(pdf), max_pages)):
            page = pdf[i]
            pil_image = page.render(scale=2.0).to_pil()
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            images.append(buf.getvalue())
        return images
    finally:
        pdf.close()


def _parse_json_lenient(text: str) -> dict:
    """Extrae el primer objeto JSON de una respuesta de texto.

    Tolera cercos de código (```json ... ```) y texto alrededor, que algunos
    proveedores agregan aunque se les pida JSON puro.
    """
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("La respuesta del modelo no contiene JSON")
        text = text[start : end + 1]
    return json.loads(text)


# =============================================================== Anthropic ===


class AnthropicProvider:
    """Backend para la API de Anthropic (Claude)."""

    def __init__(self) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=config.AI_API_KEY)

    @staticmethod
    def _first_text(response) -> str:
        if response.stop_reason == "refusal":
            raise RefusalError(
                "La solicitud fue rechazada por políticas de seguridad."
            )
        return next(b.text for b in response.content if b.type == "text")

    async def extract_document(self, data: bytes, mime_type: str) -> dict:
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
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": encoded,
                },
            }

        response = await self._client.messages.create(
            model=config.AI_MODEL,
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
        return json.loads(self._first_text(response))

    async def advise(
        self, history: list[dict], user_message: str, snapshot: str
    ) -> str:
        content = (
            f"<contexto_financiero>\n{snapshot}\n</contexto_financiero>\n\n"
            f"{user_message}"
        )
        response = await self._client.messages.create(
            model=config.AI_MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=[
                {
                    "type": "text",
                    "text": prompts.ADVISOR_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=history + [{"role": "user", "content": content}],
        )
        return self._first_text(response)


# ======================================================= OpenAI-compatible ===


class OpenAICompatProvider:
    """Backend para cualquier API compatible con OpenAI.

    Funciona con OpenAI, Gemini, Groq, DeepSeek, Mistral, OpenRouter, Ollama y
    similares configurando ``AI_BASE_URL``. Para máxima compatibilidad no usa
    parámetros exclusivos de OpenAI (como ``response_format`` con esquema): el
    JSON se pide por prompt y se parsea de forma tolerante.
    """

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=config.AI_API_KEY,
            base_url=config.AI_BASE_URL or None,
        )

    async def _chat(self, messages: list[dict]) -> str:
        response = await self._client.chat.completions.create(
            model=config.AI_MODEL,
            messages=messages,
        )
        content = response.choices[0].message.content
        if not content:
            raise RefusalError("El modelo no devolvió contenido.")
        return content

    @staticmethod
    def _image_part(data: bytes, mime_type: str) -> dict:
        encoded = base64.standard_b64encode(data).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
        }

    async def extract_document(self, data: bytes, mime_type: str) -> dict:
        if mime_type == "application/pdf":
            # No todos los proveedores compatibles con OpenAI aceptan PDFs:
            # se convierte cada página a imagen para soporte universal.
            media_parts = [
                self._image_part(page, "image/png")
                for page in _pdf_to_images(data)
            ]
        else:
            media_parts = [self._image_part(data, mime_type)]

        system = (
            prompts.EXTRACTION_SYSTEM
            + "\n\nResponde ÚNICAMENTE con un objeto JSON válido (sin texto"
            " adicional ni cercos de código) que cumpla exactamente este"
            " esquema JSON Schema:\n"
            + json.dumps(EXTRACTION_SCHEMA, ensure_ascii=False)
        )
        text = await self._chat(
            [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": media_parts
                    + [{"type": "text", "text": prompts.EXTRACTION_USER_PROMPT}],
                },
            ]
        )
        return _parse_json_lenient(text)

    async def advise(
        self, history: list[dict], user_message: str, snapshot: str
    ) -> str:
        content = (
            f"<contexto_financiero>\n{snapshot}\n</contexto_financiero>\n\n"
            f"{user_message}"
        )
        return await self._chat(
            [{"role": "system", "content": prompts.ADVISOR_SYSTEM}]
            + history
            + [{"role": "user", "content": content}]
        )


# ================================================================= fachada ===

_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "openai": OpenAICompatProvider,
}

_provider = None


def _get_provider():
    global _provider
    if _provider is None:
        _provider = _PROVIDERS[config.AI_PROVIDER]()
    return _provider


async def extract_document(data: bytes, mime_type: str) -> dict:
    """Lee una foto/PDF de un documento financiero y devuelve datos estructurados."""
    return await _get_provider().extract_document(data, mime_type)


async def advise(history: list[dict], user_message: str, snapshot: str) -> str:
    """Responde como asesor financiero usando el historial y los datos del usuario."""
    return await _get_provider().advise(history, user_message, snapshot)
