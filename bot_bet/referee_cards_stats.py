from dataclasses import dataclass
from typing import Any, Dict, List

from .api_football_client import api_football_get
from .config import settings


@dataclass
class RefereeCardsStats:
    name: str
    matches: int
    total_cards_avg: float  # tarjetas totales por partido (ponderadas)


def _get_stat_value(statistics: List[Dict[str, Any]], stat_type: str) -> int:
    """
    Extrae el valor de una estadística concreta (por ejemplo 'Yellow Cards') de la lista
    que devuelve /fixtures/statistics para un equipo.
    """
    for entry in statistics:
        if entry.get("type") == stat_type:
            value = entry.get("value")
            if value is None:
                return 0
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
    return 0


def get_referee_cards_stats(referee_name: str, last_n: int = 15) -> RefereeCardsStats:
    """
    Calcula la media de tarjetas mostradas por un árbitro en sus últimos N partidos de liga,
    usando:
      - /fixtures?league=...&season=...&referee={name}&last={N}
      - /fixtures/statistics?fixture={fixture_id}
    """
    fixtures_data = api_football_get(
        "/fixtures",
        {
            "league": settings.api_football_league_id,
            "season": settings.api_football_season,
            "referee": referee_name,
            "last": last_n,
        },
    )

    fixtures = fixtures_data.get("response", []) or []

    matches = 0
    total_cards_sum = 0

    for item in fixtures:
        fixture = item.get("fixture", {}) or {}
        fixture_id = fixture.get("id")
        if fixture_id is None:
            continue

        stats_data = api_football_get(
            "/fixtures/statistics",
            {"fixture": fixture_id},
        )

        stats_response = stats_data.get("response", []) or []
        if len(stats_response) < 2:
            continue

        # stats_response debería tener 2 entradas, una por equipo
        team1 = stats_response[0].get("statistics", []) or []
        team2 = stats_response[1].get("statistics", []) or []

        yellow1 = _get_stat_value(team1, "Yellow Cards")
        red1 = _get_stat_value(team1, "Red Cards")
        yellow2 = _get_stat_value(team2, "Yellow Cards")
        red2 = _get_stat_value(team2, "Red Cards")

        # usamos la misma idea de ponderación que en equipos: amarilla + 2*roja
        total_cards = (yellow1 + yellow2) + 2 * (red1 + red2)

        matches += 1
        total_cards_sum += total_cards

    if matches > 0:
        total_cards_avg = total_cards_sum / matches
    else:
        total_cards_avg = 0.0

    return RefereeCardsStats(
        name=referee_name,
        matches=matches,
        total_cards_avg=total_cards_avg,
    )
