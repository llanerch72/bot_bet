from bot_bet.predictions import (
    build_daily_message,
    get_todays_matches,
    build_predictions_for_match,
)
from bot_bet.telegram_client import send_message_sync


def main() -> None:
    # Mensaje completo para ver en consola
    full_text = build_daily_message()
    print("\n================ MENSAJE GENERADO ================\n")
    print(full_text)
    print("\n==================================================\n")

    # Enviar a Telegram por bloques
    matches = get_todays_matches()

    if not matches:
        # Si no hay partidos, mandamos el mensaje único estándar
        send_message_sync(full_text)
        return

    # 1) Cabecera sola
    from datetime import date
    today_str = date.today().strftime("%d/%m/%Y")
    header = f"🏆 <b>LaLiga – Pronósticos ({today_str})</b>"
    send_message_sync(header)

    # 2) Un mensaje por partido
    for match in matches:
        block = build_predictions_for_match(match)
        send_message_sync(block)


if __name__ == "__main__":
    main()
