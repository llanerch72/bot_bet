from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .api_football_client import api_football_get
from .config import settings


@dataclass
class TeamCardsStats:
    team_id: int
    matches: int
    yellow_total: int
    red_total: int
    yellow_avg: float
    red_avg: float
    cards_weighted_avg: float  # amarillas + 2 * rojas


def _safe_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _get_nested(d: Dict[str, Any], *keys: str) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _sum_card_buckets(card_dict: Any) -> int:
    """
    Suma los 'total' de todos los tramos de minutos en:
    cards.yellow / cards.red

    card_dict suele ser algo como:
    {
        "0-15":   {"total": 1, "percentage": "10.0%"},
        "16-30":  {"total": 2, "percentage": "20.0%"},
        ...
    }
    """
    if not isinstance(card_dict, dict):
        return 0

    total = 0
    for _minute_range, info in card_dict.items():
        if isinstance(info, dict):
            total += _safe_int(info.get("total"))
    return total


def get_team_cards_stats(team_id: int) -> TeamCardsStats:
    """
    Obtiene estadísticas de tarjetas de un equipo en la temporada/lig actual usando:
      - /teams/statistics?team=...&league=...&season=...

    Cálculo:
      - matches = fixtures.played.total
      - yellow_total = suma de todos los 'total' en cards.yellow
      - red_total    = suma de todos los 'total' en cards.red
      - yellow_avg = yellow_total / matches
      - red_avg    = red_total / matches
      - cards_weighted_avg = yellow_avg + 2 * red_avg
    """
    data = api_football_get(
        "/teams/statistics",
        {
            "team": team_id,
            "league": settings.api_football_league_id,
            "season": settings.api_football_season,
        },
    )

    response = data.get("response") or {}

    # Partidos jugados en liga (total: casa + fuera)
    matches = _safe_int(_get_nested(response, "fixtures", "played", "total"))

    if matches <= 0:
        print(f"[CARDS] Team {team_id}: 0 partidos registrados en la API.")
        return TeamCardsStats(
            team_id=team_id,
            matches=0,
            yellow_total=0,
            red_total=0,
            yellow_avg=0.0,
            red_avg=0.0,
            cards_weighted_avg=0.0,
        )

    cards = response.get("cards") or {}
    yellow_buckets = cards.get("yellow") or {}
    red_buckets = cards.get("red") or {}

    yellow_total = _sum_card_buckets(yellow_buckets)
    red_total = _sum_card_buckets(red_buckets)

    yellow_avg = yellow_total / matches if matches > 0 else 0.0
    red_avg = red_total / matches if matches > 0 else 0.0
    cards_weighted_avg = yellow_avg + 2 * red_avg

    print(
        f"[CARDS] Team {team_id}: matches={matches}, "
        f"yellow_total={yellow_total}, red_total={red_total}, "
        f"yellow_avg={yellow_avg:.2f}, red_avg={red_avg:.2f}, "
        f"weighted={cards_weighted_avg:.2f}"
    )

    return TeamCardsStats(
        team_id=team_id,
        matches=matches,
        yellow_total=yellow_total,
        red_total=red_total,
        yellow_avg=yellow_avg,
        red_avg=red_avg,
        cards_weighted_avg=cards_weighted_avg,
    )
