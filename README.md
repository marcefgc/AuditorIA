# AuditorIA 🤖💰

Bot de Telegram de gestión de dinero con IA. Le envías **fotos de tus facturas,
tickets, capturas de transferencias bancarias o extractos de tarjeta** (también
PDF) y él:

1. 📸 **Lee el documento con visión de IA** (Claude) y extrae cada transacción:
   monto, moneda, fecha, comercio y categoría.
2. 🗂️ **Organiza tus gastos** automáticamente en una base de datos local.
3. 💬 **Te asesora** para lograr tus objetivos financieros — ahorrar, pagar
   deudas, controlar gastos — con respuestas claras y objetivas, un tono
   empático y amigable, y consejos prácticos para evitar gastos.

## Funcionalidades

| Acción | Cómo |
|---|---|
| Registrar gastos/ingresos | Enviar foto o PDF de factura, ticket, captura o extracto |
| Resumen mensual por categoría | `/resumen` |
| Ver últimas transacciones | `/gastos` |
| Definir un objetivo financiero | `/meta ahorrar 500 USD para diciembre` |
| Ver / cumplir metas | `/metas`, `/meta_cumplida 1` |
| Borrar la última transacción | `/borrar_ultimo` |
| Consejos y análisis personalizados | Escribirle cualquier mensaje |

El asesor usa tus datos reales (gastos del mes, transacciones recientes y
metas) como contexto en cada respuesta.

## Requisitos

- Python 3.10+
- Un bot de Telegram: créalo hablando con [@BotFather](https://t.me/BotFather)
  (`/newbot`) y copia el token.
- Una API key de tu proveedor de IA favorito (ver siguiente sección).

## Proveedores de IA soportados

El bot funciona con **cualquier proveedor de IA**, configurable por variables
de entorno:

| `AI_PROVIDER` | Qué cubre | Variables |
|---|---|---|
| `anthropic` | API de Anthropic (Claude) | `AI_API_KEY`, `AI_MODEL` (def.: `claude-opus-4-8`) |
| `openai` | Cualquier API compatible con OpenAI: OpenAI, Google Gemini, Groq, DeepSeek, Mistral, OpenRouter, Ollama local... | `AI_API_KEY`, `AI_MODEL` (def.: `gpt-4o`), `AI_BASE_URL` |

> ⚠️ El modelo elegido debe soportar **visión** (entrada de imágenes) para
> poder leer las fotos de facturas.

Ejemplos de configuración en `.env`:

```bash
# Claude (Anthropic)
AI_PROVIDER=anthropic
AI_API_KEY=sk-ant-...

# OpenAI
AI_PROVIDER=openai
AI_API_KEY=sk-...
AI_MODEL=gpt-4o

# Google Gemini (endpoint compatible con OpenAI)
AI_PROVIDER=openai
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
AI_API_KEY=AIza...
AI_MODEL=gemini-2.0-flash

# Ollama local (gratis, sin API key real)
AI_PROVIDER=openai
AI_BASE_URL=http://localhost:11434/v1
AI_API_KEY=ollama
AI_MODEL=llama3.2-vision
```

Nota: la lectura de **PDF** está garantizada con `anthropic` y con la API de
OpenAI; otros proveedores compatibles pueden no aceptar PDFs (las imágenes
funcionan en todos). Si tu proveedor no soporta PDF, envía el documento como
foto.

## Instalación

```bash
git clone https://github.com/marcefgc/AuditorIA.git
cd AuditorIA

python -m venv .venv
source .venv/bin/activate  # en Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edita .env con tu TELEGRAM_BOT_TOKEN y ANTHROPIC_API_KEY
```

## Ejecutar

```bash
python -m bot.main
```

Abre tu bot en Telegram, envía `/start` y mándale tu primera factura 🧾

## Arquitectura

```
bot/
├── main.py     # Handlers de Telegram (comandos, fotos, chat)
├── ai.py       # Capa de IA con proveedores intercambiables + asesor
├── prompts.py  # Prompts de sistema (tono empático, reglas de extracción)
├── db.py       # SQLite: transacciones, metas, historial de chat
└── config.py   # Variables de entorno
```

- **Capa de IA intercambiable:** `AnthropicProvider` y `OpenAICompatProvider`
  implementan la misma interfaz (`extract_document`, `advise`); el resto del
  bot no sabe qué proveedor hay detrás.
- **Extracción estructurada:** con Anthropic se usan salidas estructuradas
  nativas (JSON Schema); con proveedores compatibles con OpenAI el esquema se
  exige por prompt y se parsea de forma tolerante, para máxima compatibilidad.
- **Privacidad:** los datos se guardan en un SQLite local (`auditoria.db`);
  nada se comparte con terceros más allá de la llamada a la API de IA elegida.

## Notas

- El bot responde en el idioma del usuario (por defecto español).
- No da recomendaciones de inversión específicas; se enfoca en presupuesto,
  ahorro y deudas.
