"""Persistencia SQLite de transacciones, metas, historial y usuarios web."""

import hashlib
import secrets
import sqlite3
from datetime import date, datetime

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    tx_date TEXT,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    tx_type TEXT NOT NULL CHECK (tx_type IN ('gasto', 'ingreso')),
    category TEXT NOT NULL,
    merchant TEXT,
    document_type TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tx_user_date ON transactions (user_id, tx_date);

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS web_users (
    user_id INTEGER PRIMARY KEY,
    display_name TEXT,
    password_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_history (user_id, id);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- transacciones

def add_transactions(user_id: int, doc: dict) -> int:
    """Guarda las transacciones extraídas de un documento. Devuelve cuántas."""
    txs = doc.get("transactions") or []
    with _connect() as conn:
        for tx in txs:
            conn.execute(
                "INSERT INTO transactions (user_id, tx_date, description, amount,"
                " currency, tx_type, category, merchant, document_type, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    tx.get("date") or date.today().isoformat(),
                    tx.get("description") or "(sin descripción)",
                    abs(float(tx.get("amount") or 0)),
                    (tx.get("currency") or "USD").upper(),
                    tx.get("type") or "gasto",
                    tx.get("category") or "otros",
                    doc.get("merchant"),
                    doc.get("document_type"),
                    _now(),
                ),
            )
    return len(txs)


def recent_transactions(user_id: int, limit: int = 15) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM transactions WHERE user_id = ?"
            " ORDER BY tx_date DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


def delete_last_transaction(user_id: int) -> sqlite3.Row | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row:
            conn.execute("DELETE FROM transactions WHERE id = ?", (row["id"],))
        return row


def month_summary(user_id: int, year: int, month: int) -> dict:
    """Totales del mes agrupados por moneda y categoría."""
    prefix = f"{year:04d}-{month:02d}"
    with _connect() as conn:
        rows = conn.execute(
            "SELECT currency, tx_type, category, SUM(amount) AS total,"
            " COUNT(*) AS n FROM transactions"
            " WHERE user_id = ? AND tx_date LIKE ?"
            " GROUP BY currency, tx_type, category ORDER BY total DESC",
            (user_id, prefix + "%"),
        ).fetchall()
    summary: dict = {}
    for r in rows:
        cur = summary.setdefault(
            r["currency"], {"gastos": {}, "ingresos": 0.0, "total_gastos": 0.0}
        )
        if r["tx_type"] == "gasto":
            cur["gastos"][r["category"]] = (
                cur["gastos"].get(r["category"], 0.0) + r["total"]
            )
            cur["total_gastos"] += r["total"]
        else:
            cur["ingresos"] += r["total"]
    return summary


def available_months(user_id: int) -> list[str]:
    """Meses (YYYY-MM) con transacciones registradas, del más reciente al más viejo."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT substr(tx_date, 1, 7) AS ym FROM transactions"
            " WHERE user_id = ? AND tx_date IS NOT NULL ORDER BY ym DESC",
            (user_id,),
        ).fetchall()
    return [r["ym"] for r in rows]


def month_transactions(
    user_id: int, year: int, month: int, limit: int = 200
) -> list[sqlite3.Row]:
    prefix = f"{year:04d}-{month:02d}"
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? AND tx_date LIKE ?"
            " ORDER BY tx_date DESC, id DESC LIMIT ?",
            (user_id, prefix + "%", limit),
        ).fetchall()


# --------------------------------------------------------------- usuarios web

_PBKDF2_ITERATIONS = 200_000


def set_web_password(
    user_id: int, password: str, display_name: str | None = None
) -> None:
    """Crea o actualiza la contraseña de acceso web del usuario."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    ).hex()
    stored = f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest}"
    with _connect() as conn:
        conn.execute(
            "INSERT INTO web_users (user_id, display_name, password_hash, updated_at)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(user_id) DO UPDATE SET"
            "  password_hash = excluded.password_hash,"
            "  display_name = COALESCE(excluded.display_name, web_users.display_name),"
            "  updated_at = excluded.updated_at",
            (user_id, display_name, stored, _now()),
        )


def get_web_user(user_id: int) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM web_users WHERE user_id = ?", (user_id,)
        ).fetchone()


def verify_web_password(user_id: int, password: str) -> bool:
    row = get_web_user(user_id)
    if not row:
        return False
    try:
        _algo, iterations, salt, digest = row["password_hash"].split("$")
        calc = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        ).hex()
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(calc, digest)


# ---------------------------------------------------------------------- metas

def add_goal(user_id: int, description: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO goals (user_id, description, created_at) VALUES (?, ?, ?)",
            (user_id, description, _now()),
        )


def list_goals(user_id: int) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM goals WHERE user_id = ? AND done = 0 ORDER BY id",
            (user_id,),
        ).fetchall()


def complete_goal(user_id: int, goal_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE goals SET done = 1 WHERE user_id = ? AND id = ?",
            (user_id, goal_id),
        )
        return cur.rowcount > 0


# ------------------------------------------------------------------ historial

def append_chat(user_id: int, role: str, content: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO chat_history (user_id, role, content, created_at)"
            " VALUES (?, ?, ?, ?)",
            (user_id, role, content, _now()),
        )
        # Conserva solo los últimos mensajes para no crecer sin límite
        conn.execute(
            "DELETE FROM chat_history WHERE user_id = ? AND id NOT IN"
            " (SELECT id FROM chat_history WHERE user_id = ?"
            "  ORDER BY id DESC LIMIT ?)",
            (user_id, user_id, config.CHAT_HISTORY_LIMIT * 2),
        )


def chat_history(user_id: int, limit: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_history WHERE user_id = ?"
            " ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
