from __future__ import annotations

from datetime import date
from time import sleep
from pathlib import Path

from bot_bet.predictions import build_daily_message
from bot_bet.telegram_client import send_message_sync

# Carpeta donde guardamos la fecha de última ejecución
RUNTIME_DIR = Path(__file__).resolve().parent / ".runtime"
LAST_RUN_FILE = RUNTIME_DIR / "last_run_date.txt"


def _load_last_run() -> str:
    try:
        return LAST_RUN_FILE.read_text().strip()
    except FileNotFoundError:
        return ""


def _save_last_run(today_str: str) -> None:
    RUNTIME_DIR.mkdir(exist_ok=True)
    LAST_RUN_FILE.write_text(today_str)


def run_once_for_today(last_run_str: str) -> str:
    """
    Si todavía no se ha ejecutado hoy, envía el mensaje y devuelve la nueva fecha de última ejecución.
    Si ya se ejecutó hoy, no hace nada y devuelve la misma fecha.
    """
    today_str = date.today().isoformat()

    if last_run_str == today_str:
        # Ya se ejecutó hoy
        return last_run_str

    print(f"[INFO] Ejecutando bot-bet para el día {today_str}...")

    text = build_daily_message()

    print("\n================ MENSAJE GENERADO ================\n")
    print(text)
    print("\n==================================================\n")

    send_message_sync(text)

    _save_last_run(today_str)
    print(f"[INFO] Ejecución completada y marcada para {today_str}.")
    return today_str


def main() -> None:
    """
    Daemon sencillo:
    - Se queda en un bucle infinito.
    - Cada X segundos comprueba si ya se ha enviado el mensaje de hoy.
    - Si no, lo envía y marca la fecha.
    """
    print("[INFO] Bot-bet daemon iniciado. Controlando ejecución 1 vez al día...")

    last_run_str = _load_last_run()

    while True:
        try:
            last_run_str = run_once_for_today(last_run_str)
        except Exception as e:
            # No queremos que el daemon muera por una excepción puntual
            print(f"[ERROR] Error en ejecución diaria: {e}")

        # Dormimos unos minutos y volvemos a comprobar
        sleep(300)  # 5 minutos


if __name__ == "__main__":
    main()
