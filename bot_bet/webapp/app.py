from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "predictions.db"

DATA_DIR.mkdir(exist_ok=True)

app = FastAPI(title="bot-bet")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                day TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()


def fetch_days(limit: int = 60) -> List[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT day FROM predictions ORDER BY day DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [r["day"] for r in rows]


def fetch_prediction(day: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT day, content, created_at FROM predictions WHERE day = ?",
            (day,),
        ).fetchone()
    return row


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    today = date.today().isoformat()
    days = fetch_days(limit=120)
    today_row = fetch_prediction(today)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "today": today,
            "today_row": today_row,
            "days": days,
        },
    )


@app.get("/day/{day}", response_class=HTMLResponse)
def day_view(day: str, request: Request):
    row = fetch_prediction(day)
    if not row:
        raise HTTPException(status_code=404, detail="No hay pronóstico guardado para ese día.")
    return templates.TemplateResponse(
        "day.html",
        {
            "request": request,
            "row": row,
        },
    )
