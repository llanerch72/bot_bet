from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from .api_football_client import api_football_get
from .config import settings
from .team_goals_stats import (
    get_team_goals_stats,
    TeamGoalsStats,
    get_team_recent_goals_stats,
    TeamRecentGoalsStats,
)
from .team_cards_stats import get_team_cards_stats, TeamCardsStats
from .referee_cards_stats import get_referee_cards_stats, RefereeCardsStats
from .team_players_cards_stats import get_team_players_cards_stats, PlayerCardsStats


MatchDict = Dict[str, Any]


# =========================
# 1. Partidos de hoy (API-Football)
# =========================

def _format_kickoff(kickoff_iso: Optional[str]) -> str:
    """
    Recibe la fecha ISO que viene de API-Football y la convierte a HH:MM.
    Si algo falla, devuelve la cadena original o un texto genérico.
    """
    if not kickoff_iso:
        return "Hora por confirmar"

    try:
        kickoff_iso = kickoff_iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(kickoff_iso)
        return dt.strftime("%H:%M")
    except Exception:
        return kickoff_iso


def get_todays_matches() -> List[MatchDict]:
    """
    Obtiene los partidos de LaLiga para la fecha de hoy usando API-Football.
    Incluye también el fixture_id y el árbitro.
    """
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")

    data = api_football_get(
        "/fixtures",
        {
            "league": settings.api_football_league_id,
            "season": settings.api_football_season,
            "date": today_str,
        },
    )

    matches: List[MatchDict] = []

    for item in data.get("response", []):
        fixture = item.get("fixture", {}) or {}
        teams = item.get("teams", {}) or {}

        home = teams.get("home", {}) or {}
        away = teams.get("away", {}) or {}

        kickoff_iso = fixture.get("date")
        kickoff_display = _format_kickoff(kickoff_iso)

        matches.append(
            {
                "fixture_id": fixture.get("id"),
                "referee": fixture.get("referee"),  # string con el nombre del árbitro
                "home_team": home.get("name"),
                "away_team": away.get("name"),
                "home_team_id": home.get("id"),
                "away_team_id": away.get("id"),
                "kickoff": kickoff_display,
            }
        )

    return matches


# =========================
# 2. Bloque de pronóstico de GOLES
# =========================

def build_goals_prediction_block(match: MatchDict) -> Tuple[str, str, float]:
    """
    Construye el bloque de GOLES para un partido y devuelve:
    - el bloque de texto
    - la apuesta candidata en goles
    - una puntuación de confianza (0.0 - 1.0)

    Combina:
    - estadísticas de la temporada (teams/statistics)
    - forma reciente (últimos N partidos vía fixtures)
    """
    home_id = match["home_team_id"]
    away_id = match["away_team_id"]
    home_name = match["home_team"]
    away_name = match["away_team"]

    if home_id is None or away_id is None:
        block_lines = [
            "🔹 Goles: Sin datos suficientes de los equipos en API-Football",
            "   💬 No se han encontrado IDs válidos de equipo para este partido.",
        ]
        return "\n".join(block_lines), "Sin apuesta clara en goles", 0.0

    # Stats de temporada
    home_season: TeamGoalsStats = get_team_goals_stats(home_id)
    away_season: TeamGoalsStats = get_team_goals_stats(away_id)

    # Forma reciente (últimos 10 partidos)
    home_recent: TeamRecentGoalsStats = get_team_recent_goals_stats(home_id, last_n=10)
    away_recent: TeamRecentGoalsStats = get_team_recent_goals_stats(away_id, last_n=10)

    # Pesos temporada / reciente según nº partidos recientes
    def compute_weights(matches_recent: int) -> Tuple[float, float]:
        if matches_recent >= 8:
            return 0.5, 0.5
        elif matches_recent >= 5:
            return 0.6, 0.4
        elif matches_recent >= 3:
            return 0.7, 0.3
        else:
            return 0.8, 0.2

    home_w_season, home_w_recent = compute_weights(home_recent.matches)
    away_w_season, away_w_recent = compute_weights(away_recent.matches)

    # % over 0.5 y 1.5 por equipo (combina temporada + reciente)
    home_over_0_5_comb = (
        home_season.over_0_5_rate * home_w_season
        + home_recent.over_0_5_rate * home_w_recent
    )
    home_over_1_5_comb = (
        home_season.over_1_5_rate * home_w_season
        + home_recent.over_1_5_rate * home_w_recent
    )

    away_over_0_5_comb = (
        away_season.over_0_5_rate * away_w_season
        + away_recent.over_0_5_rate * away_w_recent
    )
    away_over_1_5_comb = (
        away_season.over_1_5_rate * away_w_season
        + away_recent.over_1_5_rate * away_w_recent
    )

    # Combinados del partido (media de ambos equipos)
    combined_over_0_5_rate = (home_over_0_5_comb + away_over_0_5_comb) / 2
    combined_over_1_5_rate = (home_over_1_5_comb + away_over_1_5_comb) / 2

    lines: List[str] = []

    if combined_over_0_5_rate >= 0.9:
        lines.append("🔹 Goles: Más de 0.5 goles en el partido")
        lines.append(
            f"   💬 {home_name} y {away_name} presentan un porcentaje combinado altísimo de partidos con gol.\n"
            f"       • Temporada: {home_season.over_0_5_rate * 100:.0f}% / {away_season.over_0_5_rate * 100:.0f}% over 0.5\n"
            f"       • Últimos {home_recent.matches} y {away_recent.matches} partidos: "
            f"{home_recent.over_0_5_rate * 100:.0f}% / {away_recent.over_0_5_rate * 100:.0f}% over 0.5."
        )
        estrella = "Más de 0.5 goles"
        confidence = 0.95

    elif combined_over_1_5_rate >= 0.7:
        lines.append("🔹 Goles: Más de 1.5 goles en el partido")
        lines.append(
            f"   💬 El % combinado de over 1.5 es sólido considerando temporada y forma reciente.\n"
            f"       • Temporada: {home_season.over_1_5_rate * 100:.0f}% / {away_season.over_1_5_rate * 100:.0f}% over 1.5\n"
            f"       • Últimos {home_recent.matches} y {away_recent.matches} partidos: "
            f"{home_recent.over_1_5_rate * 100:.0f}% / {away_recent.over_1_5_rate * 100:.0f}% over 1.5."
        )
        estrella = "Más de 1.5 goles"
        confidence = 0.85

    else:
        lines.append("🔹 Goles: Menos de 3.5 goles en el partido")
        lines.append(
            f"   💬 Tendencia moderada en goles según temporada y forma reciente.\n"
            f"       • Temporada: {home_season.goals_for_avg + home_season.goals_against_avg:.2f} / "
            f"{away_season.goals_for_avg + away_season.goals_against_avg:.2f} goles totales de media\n"
            f"       • Últimos {home_recent.matches} y {away_recent.matches} partidos: "
            f"{home_recent.goals_for_avg + home_recent.goals_against_avg:.2f} / "
            f"{away_recent.goals_for_avg + away_recent.goals_against_avg:.2f} goles totales de media.\n"
            "       Preferimos una línea conservadora a la baja (under 3.5)."
        )
        estrella = "Menos de 3.5 goles"
        confidence = 0.65

    return "\n".join(lines), estrella, confidence


# =========================
# 3. Bloque de TARJETAS y FALTAS
# =========================

def build_cards_prediction_block(match: MatchDict) -> Tuple[str, Optional[str], float]:
    """
    Construye el bloque de TARJETAS para un partido usando:
    - estadísticas de tarjetas de los equipos (teams/statistics, cards_weighted_avg)
    - media de tarjetas del árbitro (últimos partidos)
    - jugadores más propensos a tarjeta en cada equipo

    Devuelve:
    - bloque de texto
    - apuesta candidata de tarjetas (o None si no la hay)
    - confianza (0.0 - 1.0)
    """
    home_id = match["home_team_id"]
    away_id = match["away_team_id"]
    home_name = match["home_team"]
    away_name = match["away_team"]
    referee_name = match.get("referee")

    if home_id is None or away_id is None:
        return (
            "🔹 Tarjetas: Sin datos suficientes de los equipos en API-Football\n"
            "   💬 Faltan IDs válidos de equipo para poder calcular tarjetas.",
            None,
            0.0,
        )

    home_stats: TeamCardsStats = get_team_cards_stats(home_id)
    away_stats: TeamCardsStats = get_team_cards_stats(away_id)

    # Si alguno no tiene partidos, mejor no forzar nada
    if home_stats.matches == 0 or away_stats.matches == 0:
        return (
            "🔹 Tarjetas: Sin datos suficientes de la temporada\n"
            "   💬 Alguno de los equipos tiene 0 partidos registrados en la temporada actual.",
            None,
            0.0,
        )

    combined_weighted = home_stats.cards_weighted_avg + away_stats.cards_weighted_avg

    lines: List[str] = []

    # 🔒 Caso conservador: medias muy bajas -> NO recomendar apuesta de tarjetas
    if combined_weighted < 3.0:
        lines.append("🔹 Tarjetas: Partido a priori de pocas tarjetas")
        lines.append(
            "   💬 Las medias de tarjetas de ambos equipos son bajas en la temporada actual.\n"
            f"       • {home_name}: {home_stats.yellow_avg:.2f} amarillas y {home_stats.red_avg:.2f} rojas de media\n"
            f"       • {away_name}: {away_stats.yellow_avg:.2f} amarillas y {away_stats.red_avg:.2f} rojas de media\n"
            "       Preferimos no forzar una línea alta de tarjetas en este encuentro."
        )
        cards_candidate: Optional[str] = None
        confidence = 0.4
    else:
        # Decidir la línea en función de la media combinada de tarjetas
        if combined_weighted >= 7.0:
            line_value = 5.5
            confidence = 0.85
        elif combined_weighted >= 5.5:
            line_value = 4.5
            confidence = 0.8
        elif combined_weighted >= 4.0:
            line_value = 3.5
            confidence = 0.7
        else:
            line_value = 3.5
            confidence = 0.55

        lines.append(f"🔹 Tarjetas: Más de {line_value:.1f} tarjetas totales")
        lines.append(
            "   💬 En la temporada actual, los partidos de "
            f"{home_name} y {away_name} acumulan una media combinada cercana a "
            f"{combined_weighted:.2f} tarjetas por partido "
            f"({home_name}: {home_stats.cards_weighted_avg:.2f}, "
            f"{away_name}: {away_stats.cards_weighted_avg:.2f})."
        )

        cards_candidate = f"Más de {line_value:.1f} tarjetas totales"

    # ===== Árbitro: media de tarjetas (si hay info) =====
    ref_stats: Optional[RefereeCardsStats] = None
    raw_ref_name = referee_name.strip() if isinstance(referee_name, str) else None
    print(f"[DEBUG] Árbitro para {home_name} – {away_name}: {raw_ref_name!r}")

    if raw_ref_name:
        try:
            ref_stats = get_referee_cards_stats(raw_ref_name, last_n=15)
        except Exception as e:
            print(f"[DEBUG] Error obteniendo stats del árbitro '{raw_ref_name}': {e}")
            ref_stats = None

    if ref_stats and ref_stats.matches > 0:
        lines.append(f"   👨‍⚖️ Árbitro: {ref_stats.name}")
        lines.append(
            f"       • Media de {ref_stats.total_cards_avg:.2f} tarjetas por partido "
            f"en sus últimos {ref_stats.matches} encuentros de liga."
        )

        # Ajuste suave de confianza según lo tarjetero que sea el árbitro
        if cards_candidate is not None:
            if ref_stats.total_cards_avg >= 6.5:
                confidence += 0.05
            elif ref_stats.total_cards_avg <= 4.0:
                confidence -= 0.05

    elif raw_ref_name:
        lines.append(f"   👨‍⚖️ Árbitro: {raw_ref_name}")
        lines.append(
            "       • No hay suficientes datos recientes en la API para estimar su media de tarjetas."
        )
    else:
        lines.append("   👨‍⚖️ Árbitro: Por confirmar")
        lines.append(
            "       • La API todavía no proporciona el árbitro asignado a este partido."
        )

    # Normalizar confianza
    confidence = max(0.4, min(confidence, 0.95))

    # ===== Jugadores propensos a tarjeta =====
    home_players: List[PlayerCardsStats] = []
    away_players: List[PlayerCardsStats] = []

    try:
        home_players = get_team_players_cards_stats(home_id, top_n=2)
        away_players = get_team_players_cards_stats(away_id, top_n=2)
    except Exception:
        home_players = []
        away_players = []

    if home_players or away_players:
        lines.append("   🧨 Jugadores propensos a tarjeta:")

        if home_players:
            desc = ", ".join(
                f"{p.name} ({p.total_cards} tarjetas en {p.matches} partidos, {p.cards_per_match:.2f}/partido)"
                for p in home_players
            )
            lines.append(f"       • {home_name}: {desc}")

        if away_players:
            desc = ", ".join(
                f"{p.name} ({p.total_cards} tarjetas en {p.matches} partidos, {p.cards_per_match:.2f}/partido)"
                for p in away_players
            )
            lines.append(f"       • {away_name}: {desc}")

    return "\n".join(lines), cards_candidate, confidence

def build_fouls_prediction_block(match: MatchDict) -> str:
    """
    De momento mantenemos un placeholder para FALTAS.
    """
    return (
        "🔹 Faltas: Más de 22.5 faltas totales\n"
        "   💬 Línea provisional (sin análisis detallado de faltas por ahora)."
    )


# =========================
# 4. Predicciones por partido
# =========================

def build_predictions_for_match(match: MatchDict) -> str:
    """
    Construye el bloque completo de un partido:
    - Cabecera
    - Goles
    - Tarjetas
    - Faltas
    - Apuesta estrella (elige entre goles y tarjetas)
    """
    home = match["home_team"]
    away = match["away_team"]
    kickoff = match["kickoff"]

    lines: List[str] = []

    # Separador bonito entre partidos
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    # Cabecera del partido en negrita y cursiva, con un cuadradito de color
    lines.append(f"🟩 <b>{home} – {away}</b>  <i>({kickoff})</i>")
    lines.append("")  # línea en blanco antes de los bloques de goles/tarjetas/faltas

    # 1) Goles
    goals_block, goals_star_bet, goals_conf = build_goals_prediction_block(match)
    lines.append(goals_block)

    # 2) Tarjetas
    cards_block, cards_star_bet, cards_conf = build_cards_prediction_block(match)
    lines.append(cards_block)

    # 3) Faltas (placeholder)
    fouls_block = build_fouls_prediction_block(match)
    lines.append(fouls_block)

    # 4) Apuesta estrella (según confianza)
    if goals_conf >= 0.9:
        star_bet = goals_star_bet
        star_source = "goles"
    elif cards_star_bet is not None and cards_conf > goals_conf:
        star_bet = cards_star_bet
        star_source = "tarjetas"
    else:
        star_bet = goals_star_bet
        star_source = "goles"

    lines.append(f"⭐ Apuesta estrella ({star_source}): {star_bet}")
    lines.append("   💬 Basada en la probabilidad estadística de la línea seleccionada (goles/tarjetas).")

    return "\n".join(lines)


# =========================
# 5. Mensaje diario completo
# =========================

def build_daily_message() -> str:
    """
    Construye el mensaje completo que se enviará a Telegram:
    - Título del día
    - Bloques por partido
    """
    matches = get_todays_matches()
    today_str = date.today().strftime("%d/%m/%Y")

    if not matches:
        return f"🏆 LaLiga – Pronósticos ({today_str})\n\nHoy no hay partidos de LaLiga programados."

    blocks: List[str] = [f"🏆 LaLiga – Pronósticos ({today_str})", ""]

    for idx, match in enumerate(matches, start=1):
        blocks.append(f"{idx}️⃣ {build_predictions_for_match(match)}")
        blocks.append("")  # Línea en blanco entre partidos

    return "\n".join(blocks).strip()
