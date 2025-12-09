from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List

import requests

from .config import settings
from .la_liga_client import LALIGA_COMPETITION_ID, BASE_URL


class FootballDataError(Exception):
    pass


@dataclass
class TeamFormStats:
    matches: int
    goals_for_avg: float
    goals_against_avg: float
    over_0_5_rate: float  # % de partidos con al menos 1 gol (total partido)
    over_1_5_rate: float  # % de partidos con al menos 2 goles (total partido)


def _headers() -> Dict[str, str]:
    return {"X-Auth-Token": settings.football_data_api_key}


def get_team_form_stats(team_id: int, limit: int = 10) -> TeamFormStats:
    """
    Consulta los últimos 'limit' partidos TERMINADOS de LaLiga para un equipo
    y devuelve medias de goles y % de over 0.5 / 1.5.

    Usa /v4/teams/{id}/matches de football-data.org
    """
    url = f"{BASE_URL}/teams/{team_id}/matches"
    params = {
        "status": "FINISHED",
        "competitions": LALIGA_COMPETITION_ID,
        "limit": limit,
    }

    resp = requests.get(url, headers=_headers(), params=params)
    if resp.status_code != 200:
        raise FootballDataError(
            f"Error al obtener partidos del equipo {team_id}: "
            f"{resp.status_code} - {resp.text}"
        )

    data = resp.json()
    matches_raw: List[Dict[str, Any]] = data.get("matches", [])

    if not matches_raw:
        # Sin datos → devolvemos todo a 0
        return TeamFormStats(
            matches=0,
            goals_for_avg=0.0,
            goals_against_avg=0.0,
            over_0_5_rate=0.0,
            over_1_5_rate=0.0,
        )

    # Aseguramos orden por fecha descendente (más recientes primero)
    matches_raw.sort(
        key=lambda m: datetime.fromisoformat(
            m["utcDate"].replace("Z", "+00:00")
        ),
        reverse=True,
    )

    # Nos quedamos solo con los últimos 'limit' por si vienen más
    matches_raw = matches_raw[:limit]

    total_gf = 0
    total_ga = 0
    count = 0
    over_0_5 = 0
    over_1_5 = 0

    for m in matches_raw:
        home_id = m["homeTeam"]["id"]
        away_id = m["awayTeam"]["id"]

        full_time = m.get("score", {}).get("fullTime", {})
        home_goals = full_time.get("home", 0) or 0
        away_goals = full_time.get("away", 0) or 0

        if home_id == team_id:
            gf = home_goals
            ga = away_goals
        elif away_id == team_id:
            gf = away_goals
            ga = home_goals
        else:
            # no debería pasar, pero por si acaso
            continue

        total_gf += gf
        total_ga += ga
        count += 1

        total_goals_match = home_goals + away_goals
        if total_goals_match >= 1:
            over_0_5 += 1
        if total_goals_match >= 2:
            over_1_5 += 1

    if count == 0:
        return TeamFormStats(
            matches=0,
            goals_for_avg=0.0,
            goals_against_avg=0.0,
            over_0_5_rate=0.0,
            over_1_5_rate=0.0,
        )

    return TeamFormStats(
        matches=count,
        goals_for_avg=total_gf / count,
        goals_against_avg=total_ga / count,
        over_0_5_rate=over_0_5 / count,
        over_1_5_rate=over_1_5 / count,
    )
