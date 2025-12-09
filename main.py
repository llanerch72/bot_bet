from __future__ import annotations

from datetime import date
from pathlib import Path

from bot_bet.predictions import build_daily_message
from bot_bet.telegram_client import send_message_sync

# Carpeta donde guardamos la fecha de última ejecución
RUNTIME_DIR = Path(__file__).resolve().parent / ".runtime"
LAST_RUN_FILE = RUNTIME_DIR / "last_run_date.txt"


def already_ran_today() -> bool:
    """
    Devuelve True si el bot ya se ejecutó hoy.
    Si no, guarda la fecha de hoy y devuelve False.
    """
    today_str = date.today().isoformat()

    try:
        last = LAST_RUN_FILE.read_text().strip()
    except FileNotFoundError:
        last = ""

    if last == today_str:
        print(f"[INFO] El bot ya se ejecutó hoy ({today_str}), salgo sin enviar nada.")
        return True

    # Primera ejecución del día -> guardamos fecha
    RUNTIME_DIR.mkdir(exist_ok=True)
    LAST_RUN_FILE.write_text(today_str)
    print(f"[INFO] Marcando ejecución de hoy: {today_str}")
    return False


def main() -> None:
    # Si ya se ejecutó hoy, nos vamos
    if already_ran_today():
        return

    text = build_daily_message()

    print("\n================ MENSAJE GENERADO ================\n")
    print(text)
    print("\n==================================================\n")

    send_message_sync(text)


if __name__ == "__main__":
    main()
