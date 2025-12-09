from __future__ import annotations

from typing import List
import requests

from .config import settings


# Límite de seguridad por debajo del máximo duro de Telegram (4096)
MAX_TELEGRAM_LENGTH = 4000

API_URL = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"


def _split_message(text: str, max_len: int = MAX_TELEGRAM_LENGTH) -> List[str]:
    """
    Divide un mensaje largo en varios trozos para cumplir con el límite de longitud de Telegram.

    Intenta cortar por saltos de línea para no partir frases a la mitad.
    """
    chunks: List[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break

        # Buscamos el último salto de línea antes del límite
        cut = remaining.rfind("\n", 0, max_len)
        if cut == -1:
            # Si no hay salto de línea, cortamos a pelo
            cut = max_len

        chunk = remaining[:cut]
        chunks.append(chunk.strip("\n"))

        # Avanzamos
        remaining = remaining[cut:].lstrip("\n")

    return chunks


def send_message_sync(text: str) -> None:
    """
    Envía el mensaje (posiblemente troceado) a Telegram de forma síncrona,
    usando la API HTTP directa de Telegram con parse_mode=HTML.
    """
    chunks = _split_message(text)

    for idx, chunk in enumerate(chunks, start=1):
        resp = requests.post(
            API_URL,
            data={
                "chat_id": settings.telegram_chat_id,
                "text": chunk,
                "parse_mode": "HTML",
            },
            timeout=10,
        )

        if not resp.ok:
            print(
                f"[TELEGRAM ERROR] Fallo enviando chunk {idx}/{len(chunks)}: "
                f"{resp.status_code} {resp.text}"
            )
