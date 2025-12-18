from __future__ import annotations

import json
import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from bot_bet.api_football_client import get_standings, ApiFootballError, api_football_get
from bot_bet.config import settings


# === Paths y App ===
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "predictions.db"
DATA_DIR.mkdir(exist_ok=True)

app = FastAPI(title="bot-bet")
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


# === DB helpers ===
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                day TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                payload_json TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(predictions)").fetchall()]
        if "payload_json" not in cols:
            conn.execute("ALTER TABLE predictions ADD COLUMN payload_json TEXT")
        conn.commit()


# === Payload processing ===
def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def fetch_days(limit: int = 60) -> List[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT day FROM predictions ORDER BY day DESC LIMIT ?", (limit,)).fetchall()
    return [r["day"] for r in rows]


def fetch_prediction(day: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT day, content, payload_json, created_at FROM predictions WHERE day = ?",
            (day,)
        ).fetchone()


def parse_payload(row: sqlite3.Row) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(row["payload_json"] or "")
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def split_into_match_blocks(content: str) -> List[str]:
    lines = content.splitlines()
    start_idx = next((i for i, l in enumerate(lines) if re.match(r"^\s*\d+️⃣", l)), 0)
    body = "\n".join(lines[start_idx:]).strip()
    parts = re.split(r"(?m)^\s*(?=\d+️⃣)", body)
    return [p.strip() for p in parts if p.strip()]


def extract_match_title_from_text_block(block: str) -> str:
    first_line = block.splitlines()[0].strip() if block else ""
    return re.sub(r"^\d+️⃣\s*", "", first_line)


def filter_payload_matches(payload: Dict[str, Any], pick_type="all", min_conf=0.0) -> List[Dict[str, Any]]:
    matches = payload.get("matches", [])
    if not isinstance(matches, list):
        return []

    def ok(m: Dict[str, Any]) -> bool:
        star = m.get("star", {})
        conf = _safe_float(star.get("confidence"), 0.0)
        stype = star.get("type")
        return conf >= min_conf and (pick_type == "all" or pick_type == stype)

    return [m for m in matches if isinstance(m, dict) and ok(m)]


# === Stats/trend ===
def _iter_payloads_with_day(limit_days=365) -> List[Tuple[str, Dict[str, Any]]]:
    out = []
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT day, payload_json FROM predictions ORDER BY day DESC LIMIT ?", (limit_days,)
        ).fetchall()

    for r in rows:
        try:
            p = json.loads(r["payload_json"] or "")
            if isinstance(p, dict) and isinstance(p.get("matches"), list):
                out.append((r["day"], p))
        except Exception:
            continue
    return out


def compute_trend(limit_days=30) -> List[Dict[str, Any]]:
    trend = []
    rows = _iter_payloads_with_day(limit_days=limit_days)

    for day, payload in rows:
        matches = payload.get("matches", [])
        stars_goles = sum(1 for m in matches if m.get("star", {}).get("type") == "goles")
        stars_tarjetas = sum(1 for m in matches if m.get("star", {}).get("type") == "tarjetas")
        avg_conf = sum(_safe_float(m.get("star", {}).get("confidence")) for m in matches if m.get("star")) / max(1, len(matches))

        trend.append({
            "day": day,
            "matches": len(matches),
            "stars_goles": stars_goles,
            "stars_tarjetas": stars_tarjetas,
            "avg_conf": avg_conf,
            "has_payload": True,
        })

    return trend


def compute_stats(limit_days=365) -> Dict[str, Any]:
    payloads_with_day = _iter_payloads_with_day(limit_days)
    pick_counter = {}
    team_counter = {}
    total_matches = 0
    star_conf_sum = 0.0
    star_conf_n = 0
    type_counts = {"goles": 0, "tarjetas": 0, "other": 0}

    for _, payload in payloads_with_day:
        matches = payload.get("matches", [])
        total_matches += len(matches)
        for m in matches:
            for team in [m.get("home"), m.get("away")]:
                if team:
                    team_counter[team] = team_counter.get(team, 0) + 1
            star = m.get("star", {})
            stype = star.get("type", "other")
            type_counts[stype if stype in type_counts else "other"] += 1
            conf = _safe_float(star.get("confidence"), 0.0)
            if conf:
                star_conf_sum += conf
                star_conf_n += 1
            pick = star.get("pick")
            if pick:
                pick_counter[pick] = pick_counter.get(pick, 0) + 1

    with get_conn() as conn:
        total_days = conn.execute("SELECT COUNT(*) AS n FROM predictions").fetchone()["n"]

    total_stars = sum(type_counts.values())
    return {
        "limit_days": limit_days,
        "total_days": total_days,
        "days_with_payload": len(payloads_with_day),
        "days_without_payload": total_days - len(payloads_with_day),
        "total_matches": total_matches,
        "star_type_count": type_counts,
        "total_stars": total_stars,
        "pct_goles": type_counts["goles"] / total_stars if total_stars else 0,
        "pct_tarjetas": type_counts["tarjetas"] / total_stars if total_stars else 0,
        "avg_star_confidence": star_conf_sum / star_conf_n if star_conf_n else 0.0,
        "top_picks": sorted(pick_counter.items(), key=lambda x: x[1], reverse=True)[:10],
        "top_teams": sorted(team_counter.items(), key=lambda x: x[1], reverse=True)[:12],
    }


# === Startup ===
@app.on_event("startup")
def _startup():
    init_db()


# === Vistas ===
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    today = date.today().isoformat()
    days = fetch_days(limit=120)
    today_row = fetch_prediction(today)

    pick_type = request.query_params.get("type", "all")
    try:
        min_conf = float(request.query_params.get("min_conf", "0"))
    except Exception:
        min_conf = 0.0

    payload_matches = []
    text_matches = []
    payload = None

    if today_row:
        payload = parse_payload(today_row)
        if payload and payload.get("matches") is not None:
            payload_matches = filter_payload_matches(payload, pick_type, min_conf)
        else:
            text_matches = split_into_match_blocks(today_row["content"])

    return templates.TemplateResponse("index.html", {
        "request": request,
        "today": today,
        "today_row": today_row,
        "days": days,
        "payload": payload,
        "payload_matches": payload_matches,
        "text_matches": text_matches,
        "pick_type": pick_type,
        "min_conf": min_conf,
        "extract_match_title": extract_match_title_from_text_block,
    })


@app.get("/day/{day}", response_class=HTMLResponse)
def day_view(day: str, request: Request):
    row = fetch_prediction(day)
    if not row:
        raise HTTPException(status_code=404)

    pick_type = request.query_params.get("type", "all")
    try:
        min_conf = float(request.query_params.get("min_conf", "0"))
    except Exception:
        min_conf = 0.0

    payload = parse_payload(row)
    payload_matches = filter_payload_matches(payload, pick_type, min_conf) if payload else []
    text_matches = split_into_match_blocks(row["content"]) if not payload else []

    return templates.TemplateResponse("day.html", {
        "request": request,
        "row": row,
        "payload": payload,
        "payload_matches": payload_matches,
        "text_matches": text_matches,
        "pick_type": pick_type,
        "min_conf": min_conf,
        "extract_match_title": extract_match_title_from_text_block,
    })


@app.get("/stats", response_class=HTMLResponse)
def stats_view(request: Request):
    stats = compute_stats()
    trend_30 = compute_trend()
    return templates.TemplateResponse("stats.html", {
        "request": request,
        "stats": stats,
        "trend_30": trend_30,
    })


@app.get("/standings", response_class=HTMLResponse)
def standings_view(request: Request):
    try:
        table = get_standings(settings.api_football_league_id, settings.api_football_season)
    except ApiFootballError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Error inesperado")
    return templates.TemplateResponse("standings.html", {
        "request": request,
        "table": table,
    })

@app.get("/form", response_class=HTMLResponse)
def team_form_view(request: Request, team: Optional[str] = None):
    teams = []
    selected_team = team
    matches = []
    summary = {"gf": 0, "ga": 0, "yellow_cards": 0, "red_cards": 0}
    error = None

    try:
        league_id = int(settings.api_football_league_id)
        season = int(settings.api_football_season)

        standings_data = get_standings(league_id=league_id, season=season)
        all_teams = [t["team"]["name"] for t in standings_data]
        teams = sorted(set(all_teams))

        if selected_team and selected_team in teams:
            team_id = next((t["team"]["id"] for t in standings_data if t["team"]["name"] == selected_team), None)
            if not team_id:
                raise ValueError("No se encontró el ID del equipo")

            resp = api_football_get("/fixtures", {
                "team": team_id,
                "season": season,
                "league": league_id,
                "last": 10
            })

            matches = resp["response"]

            for match in matches:
                is_home = match["teams"]["home"]["name"] == selected_team
                goals = match["goals"]
                gf = goals["home"] if is_home else goals["away"]
                ga = goals["away"] if is_home else goals["home"]
                summary["gf"] += gf
                summary["ga"] += ga

                # Obtener estadísticas del partido
                fixture_id = match["fixture"]["id"]
                stats_resp = api_football_get("/fixtures/statistics", {
                    "fixture": fixture_id
                })

                stats_list = stats_resp.get("response", [])
                match["statistics"] = stats_list

                # Contadores por partido
                match_yellow = 0
                match_red = 0

                try:
                    team_stats = next(s for s in stats_list if s["team"]["name"] == selected_team)
                    for stat in team_stats.get("statistics", []):
                        if stat["type"].lower() == "yellow cards":
                            match_yellow = stat["value"] or 0
                            summary["yellow_cards"] += match_yellow
                        elif stat["type"].lower() == "red cards":
                            match_red = stat["value"] or 0
                            summary["red_cards"] += match_red
                except Exception:
                    pass

                # Agregar al partido
                match["yellow_cards"] = match_yellow
                match["red_cards"] = match_red

    except Exception as e:
        error = str(e)

    return templates.TemplateResponse("form.html", {
        "request": request,
        "teams": teams,
        "selected_team": selected_team,
        "matches": matches,
        "summary": summary,
        "error": error,
    })
