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
- Una API key de Anthropic: [platform.claude.com](https://platform.claude.com).

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
├── ai.py       # Cliente de Claude: extracción estructurada + asesor
├── prompts.py  # Prompts de sistema (tono empático, reglas de extracción)
├── db.py       # SQLite: transacciones, metas, historial de chat
└── config.py   # Variables de entorno
```

- **Modelo de IA:** `claude-opus-4-8` con *adaptive thinking* y salidas
  estructuradas (JSON Schema) para que la extracción de documentos sea siempre
  parseable.
- **Privacidad:** los datos se guardan en un SQLite local (`auditoria.db`);
  nada se comparte con terceros más allá de la llamada a la API de IA.

## Notas

- El bot responde en el idioma del usuario (por defecto español).
- No da recomendaciones de inversión específicas; se enfoca en presupuesto,
  ahorro y deudas.
