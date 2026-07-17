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

Los **PDF funcionan con todos los proveedores**: con Anthropic se envían de
forma nativa, y con los proveedores compatibles con OpenAI el bot convierte
localmente cada página del PDF a imagen (hasta 8 páginas por documento) antes
de enviarla al modelo.

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

## Interfaz web 📱

Panel web *mobile-first* para visualizar tus datos: totales del mes, gastos por
categoría, metas y movimientos. Se ejecuta como proceso aparte y comparte la
misma base de datos del bot:

```bash
python -m web.main
# abre http://localhost:8642  (puerto configurable con WEB_PORT)
```

**Cómo entrar:**

1. En Telegram, envíale al bot `/clave <contraseña>` (mín. 6 caracteres). Eso
   crea —o actualiza— tu usuario web. El bot borra tu mensaje por seguridad.
2. El bot te responde con tu **usuario** (tu ID de Telegram) y la URL del panel.
   ¿Dudas después? `/web` te lo recuerda.
3. Entra en el panel con ese usuario y tu contraseña.

Cada sesión ve **únicamente los datos del usuario logueado**. Las contraseñas
se guardan con hash PBKDF2 y la sesión dura 30 días (cookie firmada).

Variables útiles en `.env`: `WEB_SECRET_KEY` (recomendada, para que las
sesiones sobrevivan reinicios), `WEB_URL` (la URL pública que el bot muestra),
`WEB_HOST` y `WEB_PORT`. Para exponerlo en internet usa un proxy con HTTPS
(Caddy, nginx, Cloudflare Tunnel...).

## Arquitectura

```
bot/
├── main.py     # Handlers de Telegram (comandos, fotos, chat)
├── ai.py       # Capa de IA con proveedores intercambiables + asesor
├── prompts.py  # Prompts de sistema (tono empático, reglas de extracción)
├── db.py       # SQLite: transacciones, metas, historial, usuarios web
└── config.py   # Variables de entorno
web/
├── main.py     # Punto de entrada del servidor web (python -m web.main)
├── app.py      # Rutas Flask: login, logout, dashboard
├── templates/  # HTML (login, panel)
└── static/     # CSS mobile-first con modo claro/oscuro
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
