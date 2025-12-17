from __future__ import annotations

import argparse
import sqlite3
from datetime import date
from pathlib import Path

from bot_bet.predictions import build_daily_message
from bot_bet.telegram_client import send_message_sync

# =========================
# Runtime: 1 vez al día
# =========================
RUNTIME_DIR = Path(__file__).resolve().parent / ".runtime"
LAST_RUN_FILE = RUNTIME_DIR / "last_run_date.txt"

# =========================
# SQLite: histórico web
# =========================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "predictions.db"


def get_last_run_date() -> str:
    try:
        return LAST_RUN_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def set_last_run_date(today_str: str) -> None:
    RUNTIME_DIR.mkdir(exist_ok=True)
    LAST_RUN_FILE.write_text(today_str, encoding="utf-8")


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS predictions (
            day TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def save_prediction_to_db(day: str, content: str) -> None:
    DATA_DIR.mkdir(exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    try:
        _init_db(conn)
        conn.execute(
            "INSERT OR REPLACE INTO predictions(day, content) VALUES (?, ?)",
            (day, content),
        )
        conn.commit()
    finally:
        conn.close()


def run_bot(force: bool = False) -> None:
    today_str = date.today().isoformat()
    last = get_last_run_date()

    if not force and last == today_str:
        print(f"[INFO] El bot ya se ejecutó hoy ({today_str}). No se envía nada.")
        return

    print(f"[INFO] Ejecutando bot-bet para el día {today_str} (force={force})...")

    text = build_daily_message()

    print("\n================ MENSAJE GENERADO ================\n")
    print(text)
    print("\n==================================================\n")

    # 1) Guardamos SIEMPRE en DB (aunque Telegram falle)
    try:
        save_prediction_to_db(today_str, text)
        print(f"[INFO] Guardado en DB: {DB_PATH}")
    except Exception as e:
        print(f"[ERROR] No se pudo guardar en SQLite: {e}")

    # 2) Intentamos enviar a Telegram
    try:
        send_message_sync(text)
        print("[INFO] Enviado a Telegram OK")
    except Exception as e:
        print(f"[ERROR] Error enviando a Telegram: {e}")

    # 3) Marcamos ejecución del día (siempre, para evitar spam)
    set_last_run_date(today_str)
    print(f"[INFO] Ejecución completada y marcada para {today_str}.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forzar envío aunque ya se haya ejecutado hoy",
    )
    args = parser.parse_args()
    run_bot(force=args.force)


if __name__ == "__main__":
    main()
