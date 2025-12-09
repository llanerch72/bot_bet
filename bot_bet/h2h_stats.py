from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List

import requests

from .config import settings
from .la_liga_client import BASE_URL, LALIGA_COMPETITION_ID


class FootballDataError(Exception):
    pass


@dataclass
class H2HStats:
    matches: int
    total_goals_avg: float
    over_0_5_rate: float
    over_1_5_rate: float
    over_2_5_rate: float


def _headers() -> Dict[str, str]:
    return {"X-Auth-Token": settings.football_data_api_key}

def get_h2h_stats(team_a_id: int, team_b_id: int, limit: int = 10) -> H2HStats:
    """
    Obtiene el histórico reciente de enfrentamientos directos entre team_a y team_b
    (hasta 'limit' partidos) usando football-data.org.

    Estrategia:
    - Pedimos partidos TERMINADOS del team_a (todas las competiciones).
    - Filtramos solo aquellos donde el rival es team_b.
    - Nos quedamos como máximo con los últimos 'limit' enfrentamientos directos.
    """

    url = f"{BASE_URL}/teams/{team_a_id}/matches"
    params = {
        "status": "FINISHED",
        # ojo: quitamos el filtro 'competitions' para no perder partidos de Copa, Supercopa, etc.
        "limit": 50,  # pedimos un buen histórico y luego cortamos nosotros a 'limit'
    }

    resp = requests.get(url, headers=_headers(), params=params)
    if resp.status_code != 200:
        raise FootballDataError(
            f"Error al obtener H2H ({team_a_id} vs {team_b_id}): "
            f"{resp.status_code} - {resp.text}"
        )

    data = resp.json()
    matches_raw: List[Dict[str, Any]] = data.get("matches", [])

    if not matches_raw:
        return H2HStats(
            matches=0,
            total_goals_avg=0.0,
            over_0_5_rate=0.0,
            over_1_5_rate=0.0,
            over_2_5_rate=0.0,
        )

    # ordenamos por fecha descendente
    matches_raw.sort(
        key=lambda m: datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")),
        reverse=True,
    )

    # filtramos solo partidos donde el rival es team_b
    h2h_matches: List[Dict[str, Any]] = []
    for m in matches_raw:
        home_id = m["homeTeam"]["id"]
        away_id = m["awayTeam"]["id"]

        if (home_id == team_a_id and away_id == team_b_id) or (
            home_id == team_b_id and away_id == team_a_id
        ):
            h2h_matches.append(m)

    if not h2h_matches:
        return H2HStats(
            matches=0,
            total_goals_avg=0.0,
            over_0_5_rate=0.0,
            over_1_5_rate=0.0,
            over_2_5_rate=0.0,
        )

    # nos quedamos con los últimos 'limit' enfrentamientos directos
    h2h_matches = h2h_matches[:limit]

    total_goals_sum = 0
    count = 0
    over_0_5 = 0
    over_1_5 = 0
    over_2_5 = 0

    for m in h2h_matches:
        full_time = m.get("score", {}).get("fullTime", {})
        home_goals = full_time.get("home", 0) or 0
        away_goals = full_time.get("away", 0) or 0

        total_goals = home_goals + away_goals
        total_goals_sum += total_goals
        count += 1

        if total_goals >= 1:
            over_0_5 += 1
        if total_goals >= 2:
            over_1_5 += 1
        if total_goals >= 3:
            over_2_5 += 1

    if count == 0:
        return H2HStats(
            matches=0,
            total_goals_avg=0.0,
            over_0_5_rate=0.0,
            over_1_5_rate=0.0,
            over_2_5_rate=0.0,
        )

    return H2HStats(
        matches=count,
        total_goals_avg=total_goals_sum / count,
        over_0_5_rate=over_0_5 / count,
        over_1_5_rate=over_1_5 / count,
        over_2_5_rate=over_2_5 / count,
    )
