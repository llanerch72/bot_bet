from typing import Any, Dict, Optional
import requests
from .config import settings

API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"

class ApiFootballError(Exception):
    pass

def _api_football_headers() -> Dict[str, str]:
    return {
        "x-apisports-key": settings.api_football_key,
    }

def api_football_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{API_FOOTBALL_BASE_URL}{path}"
    try:
        resp = requests.get(
            url,
            headers=_api_football_headers(),
            params=params or {},
            timeout=10,
        )
    except requests.RequestException as e:
        raise ApiFootballError(f"Error de red llamando a API-Football: {e}")

    if resp.status_code != 200:
        raise ApiFootballError(f"Error API-Football {resp.status_code}: {resp.text[:300]}")

    data = resp.json()

    # API-Football suele devolver algo como {"response": [...], "results": N, ...}
    if not isinstance(data, dict) or "response" not in data:
        raise ApiFootballError(f"Respuesta inesperada de API-Football: {data}")

    return data

def get_standings(league_id: int, season: int) -> list[dict[str, Any]]:
    """
    Devuelve la tabla de clasificación actual (posición, puntos, forma, etc.)
    """
    data = api_football_get("/standings", {"league": league_id, "season": season})
    try:
        standings = data["response"][0]["league"]["standings"][0]
        return standings
    except (KeyError, IndexError, TypeError) as e:
        raise ApiFootballError(f"No se pudo extraer clasificación: {e}")

def get_last_matches(team_id: int, season: int, league_id: int, last_n: int = 5) -> list[dict[str, Any]]:
    """
    Devuelve los últimos N partidos de un equipo en una liga y temporada.
    """
    data = api_football_get("/fixtures", {
        "team": team_id,
        "league": league_id,
        "season": season,
        "last": last_n
    })

    return data["response"]
