"""AuditorIA — bot de Telegram para organizar tus finanzas con IA.

Envíale fotos de facturas, capturas de transacciones bancarias o extractos de
tarjeta: las lee, las organiza y te ayuda a lograr tus objetivos financieros.
"""

import logging
from datetime import date

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import ai, config, db

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("auditoria")

MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

WELCOME = (
    "¡Hola! 👋 Soy AuditorIA, tu asistente financiero personal.\n\n"
    "📸 Envíame fotos de tus facturas, tickets, capturas de transferencias o "
    "extractos de tarjeta (también acepto PDF) y yo registro y organizo cada "
    "gasto por ti.\n\n"
    "💬 También puedes escribirme lo que quieras: te ayudo a ahorrar, pagar "
    "deudas y controlar tus gastos con consejos claros y sin juzgarte.\n\n"
    "Comandos útiles:\n"
    "/resumen — tus gastos del mes por categoría\n"
    "/gastos — últimas transacciones registradas\n"
    "/meta <texto> — define un objetivo (ej: /meta ahorrar 500 USD para diciembre)\n"
    "/metas — ver tus objetivos\n"
    "/borrar_ultimo — elimina la última transacción\n"
    "/clave <contraseña> — crea o cambia tu acceso a la web 📱\n"
    "/web — datos de acceso a tu panel web\n"
    "/ayuda — ver esta ayuda de nuevo\n\n"
    "¿Empezamos? Mándame tu primera factura 🧾"
)


def _fmt_amount(amount: float, currency: str) -> str:
    return f"{amount:,.2f} {currency}"


def _snapshot(user_id: int) -> str:
    """Arma el contexto financiero que se le pasa a la IA."""
    today = date.today()
    lines = [f"Fecha de hoy: {today.isoformat()}"]

    summary = db.month_summary(user_id, today.year, today.month)
    if summary:
        lines.append(f"Resumen de {MONTHS_ES[today.month - 1]} {today.year}:")
        for currency, data in summary.items():
            lines.append(
                f"- {currency}: gastos {data['total_gastos']:,.2f},"
                f" ingresos {data['ingresos']:,.2f}"
            )
            for cat, total in sorted(
                data["gastos"].items(), key=lambda kv: -kv[1]
            ):
                lines.append(f"  · {cat}: {total:,.2f}")
    else:
        lines.append("Sin transacciones registradas este mes.")

    recent = db.recent_transactions(user_id, limit=15)
    if recent:
        lines.append("Últimas transacciones:")
        for r in recent:
            sign = "-" if r["tx_type"] == "gasto" else "+"
            lines.append(
                f"- {r['tx_date']} {r['description']}"
                f" {sign}{_fmt_amount(r['amount'], r['currency'])} ({r['category']})"
            )

    goals = db.list_goals(user_id)
    if goals:
        lines.append("Metas del usuario:")
        lines.extend(f"- (#{g['id']}) {g['description']}" for g in goals)
    else:
        lines.append("El usuario aún no definió metas.")

    return "\n".join(lines)


# ------------------------------------------------------------------- comandos

async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME)


async def cmd_resumen(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    today = date.today()
    summary = db.month_summary(user_id, today.year, today.month)
    if not summary:
        await update.message.reply_text(
            "Todavía no tengo transacciones registradas este mes. "
            "Envíame una foto de una factura o captura bancaria para empezar 📸"
        )
        return

    lines = [f"📊 Resumen de {MONTHS_ES[today.month - 1]} {today.year}\n"]
    for currency, data in summary.items():
        lines.append(f"💱 {currency}")
        for cat, total in sorted(data["gastos"].items(), key=lambda kv: -kv[1]):
            lines.append(f"  • {cat}: {_fmt_amount(total, currency)}")
        lines.append(f"  Total gastos: {_fmt_amount(data['total_gastos'], currency)}")
        if data["ingresos"]:
            lines.append(f"  Ingresos: {_fmt_amount(data['ingresos'], currency)}")
        lines.append("")
    lines.append("💡 Pregúntame qué gasto podrías recortar si quieres un consejo.")
    await update.message.reply_text("\n".join(lines))


async def cmd_gastos(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    rows = db.recent_transactions(update.effective_user.id, limit=15)
    if not rows:
        await update.message.reply_text(
            "Aún no hay transacciones. Envíame una foto de una factura para "
            "registrar la primera 🧾"
        )
        return
    lines = ["🧾 Últimas transacciones:\n"]
    for r in rows:
        sign = "−" if r["tx_type"] == "gasto" else "+"
        lines.append(
            f"{r['tx_date']} · {r['description']} · "
            f"{sign}{_fmt_amount(r['amount'], r['currency'])}"
        )
    await update.message.reply_text("\n".join(lines))


async def cmd_meta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text(
            "Escribe tu objetivo después del comando, por ejemplo:\n"
            "/meta ahorrar 500 USD para diciembre"
        )
        return
    db.add_goal(update.effective_user.id, text)
    await update.message.reply_text(
        f"✅ ¡Meta registrada! «{text}»\n\n"
        "La tendré en cuenta en mis consejos. Puedes verla con /metas."
    )


async def cmd_metas(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    goals = db.list_goals(update.effective_user.id)
    if not goals:
        await update.message.reply_text(
            "No tienes metas activas. Crea una con:\n/meta ahorrar 500 USD para diciembre"
        )
        return
    lines = ["🎯 Tus metas:\n"]
    lines.extend(f"#{g['id']} — {g['description']}" for g in goals)
    lines.append("\nMarca una como cumplida con /meta_cumplida <número>")
    await update.message.reply_text("\n".join(lines))


async def cmd_meta_cumplida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or not context.args[0].lstrip("#").isdigit():
        await update.message.reply_text("Uso: /meta_cumplida <número de meta>")
        return
    goal_id = int(context.args[0].lstrip("#"))
    if db.complete_goal(update.effective_user.id, goal_id):
        await update.message.reply_text("🎉 ¡Felicitaciones! Meta cumplida. A por la siguiente 💪")
    else:
        await update.message.reply_text("No encontré esa meta. Revisa el número con /metas.")


async def cmd_borrar_ultimo(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    row = db.delete_last_transaction(update.effective_user.id)
    if row:
        await update.message.reply_text(
            f"🗑️ Eliminada: {row['description']} "
            f"({_fmt_amount(row['amount'], row['currency'])})"
        )
    else:
        await update.message.reply_text("No hay transacciones para eliminar.")


async def cmd_clave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Crea o actualiza la contraseña del panel web."""
    user = update.effective_user
    password = " ".join(context.args).strip()

    # Borra el mensaje que contiene la contraseña, por seguridad
    try:
        await update.message.delete()
    except Exception:
        pass

    if not password:
        await update.effective_chat.send_message(
            "Uso: /clave <contraseña>\n\n"
            "Crea (o cambia) tu contraseña para entrar al panel web. "
            "Mínimo 6 caracteres. Ejemplo:\n/clave MiClaveSegura123"
        )
        return
    if len(password) < 6:
        await update.effective_chat.send_message(
            "La contraseña debe tener al menos 6 caracteres 🔒 Intenta de nuevo."
        )
        return

    is_new = db.get_web_user(user.id) is None
    db.set_web_password(user.id, password, user.first_name)
    action = "creado" if is_new else "actualizado"
    await update.effective_chat.send_message(
        f"🔐 ¡Acceso web {action}! (borré tu mensaje por seguridad)\n\n"
        f"🌐 Panel: {config.WEB_URL}\n"
        f"👤 Usuario: {user.id}\n"
        "🔑 Contraseña: la que acabas de definir\n\n"
        "Puedes cambiarla cuando quieras con /clave <nueva contraseña>."
    )


async def cmd_web(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra los datos de acceso al panel web."""
    user = update.effective_user
    if db.get_web_user(user.id) is None:
        await update.message.reply_text(
            "Aún no tienes acceso web. Créalo con:\n/clave <contraseña>\n\n"
            "Luego entra con tu número de usuario y esa contraseña."
        )
        return
    await update.message.reply_text(
        f"🌐 Tu panel web: {config.WEB_URL}\n"
        f"👤 Usuario: {user.id}\n"
        "🔑 Contraseña: la definida con /clave\n\n"
        "¿La olvidaste? Cámbiala con /clave <nueva contraseña>."
    )


# ----------------------------------------------------------------- documentos

MAX_FILE_BYTES = 20 * 1024 * 1024  # límite de descarga de la Bot API


async def handle_document_photo(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa fotos y archivos (imagen/PDF) con documentos financieros."""
    user_id = update.effective_user.id
    message = update.message

    if message.photo:
        tg_file = await message.photo[-1].get_file()
        mime_type = "image/jpeg"
    else:
        doc = message.document
        if doc.file_size and doc.file_size > MAX_FILE_BYTES:
            await message.reply_text("El archivo es muy grande (máx. 20 MB) 😅")
            return
        tg_file = await doc.get_file()
        mime_type = doc.mime_type or "image/jpeg"
        if (doc.file_name or "").lower().endswith(".pdf"):
            mime_type = "application/pdf"

    await message.chat.send_action(ChatAction.TYPING)
    status = await message.reply_text("🔍 Leyendo tu documento, dame unos segundos...")

    try:
        data = bytes(await tg_file.download_as_bytearray())
        result = await ai.extract_document(data, mime_type)
    except ai.RefusalError:
        await status.edit_text(
            "No pude procesar este documento por políticas de seguridad. "
            "Prueba con otra imagen 🙏"
        )
        return
    except Exception:
        logger.exception("Error extrayendo documento")
        await status.edit_text(
            "Ups, tuve un problema leyendo el documento 😓 "
            "¿Puedes intentar con una foto más nítida?"
        )
        return

    if not result.get("is_financial_document") or not result.get("transactions"):
        await status.edit_text(
            "Mmm, no encontré datos financieros en esa imagen 🤔\n"
            "Envíame una factura, ticket, captura de transferencia o extracto "
            "y lo registro al instante."
        )
        return

    count = db.add_transactions(user_id, result)
    txs = result["transactions"]
    lines = [f"✅ ¡Listo! Registré {count} transacción(es):\n"]
    for tx in txs[:10]:
        sign = "−" if tx["type"] == "gasto" else "+"
        lines.append(
            f"• {tx['description']}: {sign}{_fmt_amount(tx['amount'], tx['currency'])}"
            f" ({tx['category']})"
        )
    if count > 10:
        lines.append(f"...y {count - 10} más.")
    if result.get("notes"):
        lines.append(f"\n📝 Nota: {result['notes']}")
    lines.append("\nUsa /resumen para ver tu mes, o pregúntame lo que quieras 💬")
    await status.edit_text("\n".join(lines))

    # Deja constancia en el historial para que el asesor tenga continuidad
    db.append_chat(
        user_id,
        "assistant",
        f"[Registré {count} transacciones de un documento tipo "
        f"{result.get('document_type')} de {result.get('merchant') or 'origen desconocido'}]",
    )


# ----------------------------------------------------------------- chat libre

def _valid_transactions(raw: list) -> list[dict]:
    """Filtra las transacciones del chat: monto numérico positivo obligatorio."""
    valid = []
    for tx in raw or []:
        if not isinstance(tx, dict):
            continue
        try:
            if float(tx.get("amount") or 0) > 0:
                valid.append(tx)
        except (TypeError, ValueError):
            continue
    return valid


async def handle_text(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text

    await update.message.chat.send_action(ChatAction.TYPING)
    history = db.chat_history(user_id, config.CHAT_HISTORY_LIMIT)
    try:
        result = await ai.chat(history, text, _snapshot(user_id))
    except ai.RefusalError:
        await update.message.reply_text(
            "No puedo ayudarte con eso, pero con gusto hablamos de tus "
            "finanzas 💬"
        )
        return
    except Exception:
        logger.exception("Error generando consejo")
        await update.message.reply_text(
            "Tuve un problema para responder 😓 Intenta de nuevo en un momento."
        )
        return

    reply = (result.get("reply") or "").strip() or "¿Me lo repites? 🙏"

    # Movimientos declarados por texto ("gasté 50mil en cena") -> a la base,
    # así aparecen también en /resumen y en el dashboard web.
    txs = _valid_transactions(result.get("transactions"))
    if txs:
        db.add_transactions(
            user_id,
            {"document_type": "chat", "merchant": None, "transactions": txs},
        )
        lines = [reply, "", "✍️ Registrado:"]
        for tx in txs:
            sign = "−" if tx.get("type") != "ingreso" else "+"
            lines.append(
                f"• {tx.get('description', 'movimiento')}: "
                f"{sign}{_fmt_amount(float(tx['amount']), (tx.get('currency') or 'USD').upper())}"
                f" ({tx.get('category', 'otros')})"
            )
        reply = "\n".join(lines)

    db.append_chat(user_id, "user", text)
    db.append_chat(user_id, "assistant", reply)
    await update.message.reply_text(reply)


# --------------------------------------------------------------------- set-up

def main() -> None:
    config.validate()
    db.init_db()

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler(["start", "ayuda", "help"], cmd_start))
    app.add_handler(CommandHandler("resumen", cmd_resumen))
    app.add_handler(CommandHandler("gastos", cmd_gastos))
    app.add_handler(CommandHandler("meta", cmd_meta))
    app.add_handler(CommandHandler("metas", cmd_metas))
    app.add_handler(CommandHandler("meta_cumplida", cmd_meta_cumplida))
    app.add_handler(CommandHandler("borrar_ultimo", cmd_borrar_ultimo))
    app.add_handler(CommandHandler("clave", cmd_clave))
    app.add_handler(CommandHandler("web", cmd_web))
    app.add_handler(
        MessageHandler(
            filters.PHOTO
            | filters.Document.IMAGE
            | filters.Document.MimeType("application/pdf")
            | filters.Document.FileExtension("pdf"),
            handle_document_photo,
        )
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("AuditorIA en marcha 🚀")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
