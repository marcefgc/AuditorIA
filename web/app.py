"""Interfaz web de AuditorIA (mobile-first).

Comparte la base SQLite con el bot. Las credenciales se crean y modifican
desde Telegram con /clave; aquí solo se valida el login y se muestran los
datos del usuario autenticado.
"""

import re
import secrets
from datetime import date, timedelta

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from bot import config, db

MONTHS_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

CATEGORY_EMOJI = {
    "alimentacion": "🛒",
    "restaurantes": "🍽️",
    "transporte": "🚌",
    "vivienda": "🏠",
    "servicios": "💡",
    "suscripciones": "📺",
    "salud": "🩺",
    "educacion": "📚",
    "entretenimiento": "🎮",
    "ropa": "👕",
    "viajes": "✈️",
    "deudas": "💳",
    "ahorro": "🐖",
    "transferencias": "🔁",
    "otros": "📦",
}

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _month_label(ym: str) -> str:
    year, month = ym.split("-")
    return f"{MONTHS_ES[int(month) - 1]} {year}"


def _fmt_tile(value: float, signed: bool = False) -> str:
    """Importe compacto para las tarjetas: sin decimales cuando es grande."""
    spec = "+,.0f" if signed else ",.0f"
    if abs(value) < 1000:
        spec = "+,.2f" if signed else ",.2f"
    return format(value, spec)


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = config.WEB_SECRET_KEY or secrets.token_hex(32)
    app.permanent_session_lifetime = timedelta(days=30)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    db.init_db()

    if not config.WEB_SECRET_KEY:
        app.logger.warning(
            "WEB_SECRET_KEY no está definida: las sesiones se cerrarán en cada"
            " reinicio del servidor."
        )

    # ------------------------------------------------------------------ auth

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            user_id_raw = (request.form.get("user_id") or "").strip()
            password = request.form.get("password") or ""
            if not user_id_raw.isdigit() or not db.verify_web_password(
                int(user_id_raw), password
            ):
                flash("Usuario o contraseña incorrectos.")
                return render_template("login.html"), 401
            session.clear()
            session["user_id"] = int(user_id_raw)
            session.permanent = True
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ------------------------------------------------------------- dashboard

    @app.get("/")
    def dashboard():
        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("login"))

        months = db.available_months(user_id)
        current = date.today().strftime("%Y-%m")
        selected = request.args.get("mes", "")
        if not _MONTH_RE.match(selected):
            selected = months[0] if months else current
        if selected not in months:
            months = sorted(set(months) | {selected}, reverse=True)

        year, month = int(selected[:4]), int(selected[5:7])
        summary = db.month_summary(user_id, year, month)
        transactions = db.month_transactions(user_id, year, month)
        goals = db.list_goals(user_id)
        web_user = db.get_web_user(user_id)

        # Estructura por moneda para las tarjetas y barras de categorías
        currencies = []
        for cur, data in summary.items():
            cats = sorted(data["gastos"].items(), key=lambda kv: -kv[1])
            max_amount = cats[0][1] if cats else 1.0
            balance = data["ingresos"] - data["total_gastos"]
            currencies.append(
                {
                    "code": cur,
                    "expenses": _fmt_tile(data["total_gastos"]),
                    "income": _fmt_tile(data["ingresos"]),
                    "balance": _fmt_tile(balance, signed=True),
                    "categories": [
                        {
                            "name": name,
                            "emoji": CATEGORY_EMOJI.get(name, "📦"),
                            "amount": amount,
                            "pct": round(amount / max_amount * 100),
                            "share": (
                                round(amount / data["total_gastos"] * 100)
                                if data["total_gastos"]
                                else 0
                            ),
                        }
                        for name, amount in cats
                    ],
                }
            )

        return render_template(
            "dashboard.html",
            display_name=(web_user["display_name"] if web_user else None) or "👋",
            months=[{"value": m, "label": _month_label(m)} for m in months],
            selected=selected,
            selected_label=_month_label(selected),
            currencies=currencies,
            transactions=transactions,
            goals=goals,
            category_emoji=CATEGORY_EMOJI,
        )

    return app
