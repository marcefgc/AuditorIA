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

# Iconos Material Symbols por categoría (ver templates/base.html)
CATEGORY_ICON = {
    "alimentacion": "shopping_cart",
    "restaurantes": "restaurant",
    "transporte": "directions_bus",
    "vivienda": "home",
    "servicios": "bolt",
    "suscripciones": "subscriptions",
    "salud": "medical_services",
    "educacion": "school",
    "entretenimiento": "sports_esports",
    "ropa": "checkroom",
    "viajes": "flight",
    "deudas": "credit_card",
    "ahorro": "savings",
    "transferencias": "sync_alt",
    "otros": "category",
}

# Monedas sin subunidad en uso: los importes se muestran sin decimales.
ZERO_DECIMAL_CURRENCIES = {"PYG", "CLP", "JPY", "KRW", "VND"}

MONTHS_ES_SHORT = [
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
]

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _month_label(ym: str) -> str:
    year, month = ym.split("-")
    return f"{MONTHS_ES[int(month) - 1]} {year}"


def _decimals(currency: str) -> int:
    return 0 if currency.upper() in ZERO_DECIMAL_CURRENCIES else 2


def _fmt_amount(value: float, currency: str, signed: bool = False) -> str:
    """Importe con separadores es-PY: 1.234.567,89 (sin decimales en PYG)."""
    spec = f"{'+' if signed else ''},.{_decimals(currency)}f"
    s = format(value, spec)
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _fmt_tile(value: float, currency: str, signed: bool = False) -> str:
    """Importe compacto para las tarjetas: sin decimales cuando es grande."""
    nd = _decimals(currency)
    if nd and abs(value) >= 1000:
        nd = 0
    spec = f"{'+' if signed else ''},.{nd}f"
    s = format(value, spec)
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _fmt_tx_date(tx_date: str) -> str:
    """'2026-07-16' -> '16 jul'."""
    try:
        _, month, day = tx_date[:10].split("-")
        return f"{int(day)} {MONTHS_ES_SHORT[int(month) - 1]}"
    except (ValueError, IndexError):
        return tx_date


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
                    "expenses": _fmt_tile(data["total_gastos"], cur),
                    "income": _fmt_tile(data["ingresos"], cur),
                    "balance": _fmt_tile(balance, cur, signed=True),
                    "categories": [
                        {
                            "name": name,
                            "icon": CATEGORY_ICON.get(name, "category"),
                            "amount": _fmt_amount(amount, cur),
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

        # Movimientos con importe, fecha e icono ya formateados
        tx_view = []
        for tx in transactions:
            income = tx["tx_type"] == "ingreso"
            tx_view.append(
                {
                    "description": tx["description"],
                    "category": tx["category"],
                    "date": _fmt_tx_date(tx["tx_date"]),
                    "income": income,
                    "amount": _fmt_amount(tx["amount"], tx["currency"]),
                    "currency": tx["currency"],
                    "icon": (
                        "payments"
                        if income
                        else CATEGORY_ICON.get(tx["category"], "category")
                    ),
                }
            )

        return render_template(
            "dashboard.html",
            display_name=(web_user["display_name"] if web_user else None) or "",
            months=[{"value": m, "label": _month_label(m)} for m in months],
            selected=selected,
            selected_label=_month_label(selected),
            currencies=currencies,
            transactions=tx_view,
            goals=goals,
        )

    return app
