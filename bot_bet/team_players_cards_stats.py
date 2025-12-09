from dataclasses import dataclass
from typing import Any, Dict, List

from .api_football_client import api_football_get
from .config import settings


@dataclass
class PlayerCardsStats:
    name: str
    matches: int
    yellow: int
    red: int
    total_cards: int
    cards_per_match: float


def get_team_players_cards_stats(
    team_id: int,
    top_n: int = 3,
    min_matches: int = 5,
    min_cards: int = 3,
) -> List[PlayerCardsStats]:
    """
    Devuelve los jugadores más propensos a tarjeta de un equipo en la temporada,
    usando /players?team=...&season=...

    Filtra por:
      - mínimo de partidos jugados
      - mínimo de tarjetas acumuladas
    """
    data = api_football_get(
        "/players",
        {
            "team": team_id,
            "season": settings.api_football_season,
        },
    )

    response = data.get("response", []) or []

    players_stats: List[PlayerCardsStats] = []

    for item in response:
        player = item.get("player", {}) or {}
        stats_list = item.get("statistics", []) or []
        if not stats_list:
            continue

        stats = stats_list[0]
        games = stats.get("games", {}) or {}
        cards = stats.get("cards", {}) or {}

        matches = games.get("appearences") or 0  # API-Football usa 'appearences'
        yellow = cards.get("yellow") or 0
        red = cards.get("red") or 0
        total_cards = yellow + red

        if matches == 0 or total_cards == 0:
            continue
        if matches < min_matches and total_cards < min_cards:
            continue

        cards_per_match = total_cards / matches

        players_stats.append(
            PlayerCardsStats(
                name=player.get("name") or "Jugador",
                matches=matches,
                yellow=yellow,
                red=red,
                total_cards=total_cards,
                cards_per_match=cards_per_match,
            )
        )

    # Ordenamos por tarjetas/partido desc, y luego por total de tarjetas desc
    players_stats.sort(
        key=lambda p: (p.cards_per_match, p.total_cards),
        reverse=True,
    )

    return players_stats[:top_n]
