from __future__ import annotations

from datetime import date
from pathlib import Path
import argparse

from bot_bet.predictions import build_daily_message
from bot_bet.telegram_client import send_message_sync

# Carpeta donde guardamos la fecha de última ejecución
RUNTIME_DIR = Path(__file__).resolve().parent / ".runtime"
LAST_RUN_FILE = RUNTIME_DIR / "last_run_date.txt"


def get_last_run_date() -> str:
    try:
        return LAST_RUN_FILE.read_text().strip()
    except FileNotFoundError:
        return ""


def set_last_run_date(today_str: str) -> None:
    RUNTIME_DIR.mkdir(exist_ok=True)
    LAST_RUN_FILE.write_text(today_str)


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

    send_message_sync(text)
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
