from typing import Optional, Dict

TEAM_ID_MAP = {
    "FC Barcelona": 529,
    "Club Atlético de Madrid": 530,
    "Athletic Club": 531,
    "Valencia CF": 532,
    "Villarreal CF": 533,
    "Sevilla FC": 536,
    "RC Celta de Vigo": 538,
    "Levante UD": 539,
    "RCD Espanyol": 540,
    "Real Madrid": 541,
    "Deportivo Alavés": 542,
    "Real Betis": 543,
    "Getafe CF": 546,
    "Girona FC": 547,
    "Real Sociedad": 548,
    "Real Oviedo": 718,
    "CA Osasuna": 727,
    "Rayo Vallecano": 728,
    "Elche CF": 797,
    "RCD Mallorca": 798,
}

def get_api_team_id(team_name: str) -> Optional[int]:
    team_id = TEAM_ID_MAP.get(team_name)
    if team_id is None:
        print(f"[TEAM_ID_MAP] No API-Football ID para '{team_name}'")
    else:
        print(f"[TEAM_ID_MAP] {team_name} -> {team_id}")
    return team_id
