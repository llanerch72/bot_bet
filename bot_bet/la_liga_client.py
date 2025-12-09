from datetime import datetime, date
from typing import List, Dict

import requests

from .config import settings

# En football-data.org LaLiga suele tener el código 2014.
LALIGA_COMPETITION_ID = 2014
BASE_URL = "https://api.football-data.org/v4"


class FootballDataError(Exception):
    pass


def _get_headers() -> Dict[str, str]:
    return {
        "X-Auth-Token": settings.football_data_api_key
    }


def get_laliga_matches_for_date(target_date: date) -> List[Dict]:
    """
    Devuelve la lista de partidos de LaLiga para una fecha concreta usando football-data.org.
    Cada partido se simplifica a un dict con: home_team, away_team, kickoff.
    """
    # football-data.org v4 usa parámetros dateFrom y dateTo en formato YYYY-MM-DD
    day_str = target_date.strftime("%Y-%m-%d")
    url = f"{BASE_URL}/competitions/{LALIGA_COMPETITION_ID}/matches"

    params = {
        "dateFrom": day_str,
        "dateTo": day_str,
        # opcionalmente se podría filtrar por estado: SCHEDULED, LIVE, FINISHED, etc.
        "status": "SCHEDULED"
    }

    response = requests.get(url, headers=_get_headers(), params=params)

    if response.status_code != 200:
        raise FootballDataError(
            f"Error en football-data.org: {response.status_code} - {response.text}"
        )

    data = response.json()
    matches_raw = data.get("matches", [])

    matches: List[Dict] = []

    for m in matches_raw:
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]
        home_id = m["homeTeam"]["id"]
        away_id = m["awayTeam"]["id"]
        utc_date = m["utcDate"]  # ej: "2025-12-01T20:00:00Z"

        kickoff_time = _extract_time_from_utc(utc_date)

        matches.append(
            {
                "home_team": home,
                "away_team": away,
                "home_team_id": home_id,
                "away_team_id": away_id,
                "kickoff": kickoff_time,
            }
        )
    return matches


def _extract_time_from_utc(utc_iso: str) -> str:
    """
    Recibe algo tipo '2025-12-01T20:00:00Z' y devuelve '20:00'.
    (Sin conversión de zona horaria todavía).
    """
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except Exception:
        # Por si acaso, devolver tal cual parte de la cadena
        return utc_iso[11:16]
