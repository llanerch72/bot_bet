from dataclasses import dataclass
from typing import Any, Dict, Optional

from .api_football_client import api_football_get
from .config import settings


# =========================
# 1. Estadísticas de GOLES de la TEMPORADA (teams/statistics)
# =========================

@dataclass
class TeamGoalsStats:
    matches: int
    goals_for_avg: float
    goals_against_avg: float
    over_0_5_rate: float  # 0.0 - 1.0
    over_1_5_rate: float  # 0.0 - 1.0


from typing import Union

def _safe_float(value: Optional[Union[str, int, float]]) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def get_team_goals_stats(team_id: int) -> TeamGoalsStats:
    """
    Usa /teams/statistics de API-Football para sacar:
    - partidos jugados
    - media de goles a favor/en contra
    - % aproximado de over 0.5 y over 1.5 (según datos de la API)

    NOTA: Ajusta los campos concretos de over_0_5 / over_1_5 según
    el formato exacto que te devuelva tu suscripción de API-Football.
    """
    data = api_football_get(
        "/teams/statistics",
        {
            "league": settings.api_football_league_id,
            "season": settings.api_football_season,
            "team": team_id,
        },
    )

    stats = data.get("response", {})

    fixtures = stats.get("fixtures", {}) or {}
    played_total = fixtures.get("played", {}).get("total", 0) or 0

    goals = stats.get("goals", {}) or {}
    goals_for = goals.get("for", {}) or {}
    goals_against = goals.get("against", {}) or {}

    goals_for_avg_total = _safe_float(goals_for.get("average", {}).get("total"))
    goals_against_avg_total = _safe_float(goals_against.get("average", {}).get("total"))

    # 🔧 Aquí depende del formato real de la API.
    # Dejo una estructura genérica que puedes ajustar a tu JSON real.
    #
    # Ejemplo orientativo (si tu JSON tiene algo tipo "over_0_5": {"total": X, ...}):
    over_stats_for = goals_for.get("total", {}) or {}

    over_0_5 = over_stats_for.get("over_0_5")
    over_1_5 = over_stats_for.get("over_1_5")

    if isinstance(over_0_5, dict):
        over_0_5 = over_0_5.get("total")
    if isinstance(over_1_5, dict):
        over_1_5 = over_1_5.get("total")

    over_0_5 = over_0_5 or 0
    over_1_5 = over_1_5 or 0

    over_0_5_rate = (over_0_5 / played_total) if played_total else 0.0
    over_1_5_rate = (over_1_5 / played_total) if played_total else 0.0

    return TeamGoalsStats(
        matches=played_total,
        goals_for_avg=goals_for_avg_total,
        goals_against_avg=goals_against_avg_total,
        over_0_5_rate=over_0_5_rate,
        over_1_5_rate=over_1_5_rate,
    )


# =========================
# 2. Forma reciente (últimos N partidos) vía /fixtures
# =========================

@dataclass
class TeamRecentGoalsStats:
    matches: int
    goals_for_avg: float
    goals_against_avg: float
    over_0_5_rate: float  # 0.0 - 1.0
    over_1_5_rate: float  # 0.0 - 1.0


def get_team_recent_goals_stats(team_id: int, last_n: int = 10) -> TeamRecentGoalsStats:
    """
    Usa /fixtures?team={id}&last={N} para sacar forma reciente de GOLES:
    - media de goles a favor/en contra en los últimos N partidos
    - % over 0.5 / 1.5 en esos partidos
    """
    data = api_football_get(
        "/fixtures",
        {
            "team": team_id,
            "season": settings.api_football_season,
            "league": settings.api_football_league_id,
            "last": last_n,
        },
    )

    fixtures = data.get("response", []) or []

    matches = 0
    goals_for_total = 0
    goals_against_total = 0
    over_0_5_count = 0
    over_1_5_count = 0

    for item in fixtures:
        goals = item.get("goals", {}) or {}
        teams = item.get("teams", {}) or {}
        home = teams.get("home", {}) or {}
        away = teams.get("away", {}) or {}

        home_id = home.get("id")
        away_id = away.get("id")

        gf = 0
        ga = 0

        if home_id == team_id:
            gf = goals.get("home") or 0
            ga = goals.get("away") or 0
        elif away_id == team_id:
            gf = goals.get("away") or 0
            ga = goals.get("home") or 0
        else:
            # Partido que no corresponde a este equipo (no debería pasar, pero por si acaso)
            continue

        try:
            gf = int(gf)
            ga = int(ga)
        except (TypeError, ValueError):
            continue

        total_goals = gf + ga

        matches += 1
        goals_for_total += gf
        goals_against_total += ga

        if total_goals >= 1:
            over_0_5_count += 1
        if total_goals >= 2:
            over_1_5_count += 1

    if matches > 0:
        goals_for_avg = goals_for_total / matches
        goals_against_avg = goals_against_total / matches
        over_0_5_rate = over_0_5_count / matches
        over_1_5_rate = over_1_5_count / matches
    else:
        goals_for_avg = 0.0
        goals_against_avg = 0.0
        over_0_5_rate = 0.0
        over_1_5_rate = 0.0

    return TeamRecentGoalsStats(
        matches=matches,
        goals_for_avg=goals_for_avg,
        goals_against_avg=goals_against_avg,
        over_0_5_rate=over_0_5_rate,
        over_1_5_rate=over_1_5_rate,
    )
