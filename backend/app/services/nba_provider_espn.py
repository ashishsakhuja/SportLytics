from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.settings import settings


@dataclass(frozen=True)
class NBAGameRow:
    eid: str
    season: int
    season_type: str  # "REG" | "POST" | "PRE"
    game_date: Optional[datetime]

    home: str
    away: str
    home_score: Optional[int]
    away_score: Optional[int]

    status: str  # pre | live | final
    phase: Optional[str]
    source_url: str


def _parse_utc(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        if dt_str.endswith("Z"):
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(dt_str)
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


def _to_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(x)
    except Exception:
        return None


def _map_status(espn_status: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    st = (espn_status.get("type") or {}).get("state") or ""
    completed = (espn_status.get("type") or {}).get("completed")
    detail = (espn_status.get("type") or {}).get("detail")

    if completed is True:
        return "final", detail
    if st == "in":
        return "live", detail
    return "pre", detail


def _infer_nba_season_year(game_dt: Optional[datetime]) -> int:
    """
    Store NBA season as the *ending year* (e.g., Oct 2024 -> 2025 season).
    If date missing, fall back to current year.
    """
    if not game_dt:
        return datetime.utcnow().year
    # NBA regular season starts in Oct and runs into next year
    return game_dt.year + 1 if game_dt.month >= 8 else game_dt.year


def _map_season_type(payload: Dict[str, Any]) -> str:
    # ESPN often includes payload["season"]["type"] (1 pre, 2 reg, 3 post)
    st = (payload.get("season") or {}).get("type")
    if st == 1:
        return "PRE"
    if st == 3:
        return "POST"
    return "REG"


async def fetch_espn_nba_scoreboard(*, date_yyyymmdd: str) -> Dict[str, Any]:
    """
    ESPN NBA scoreboard supports query param: dates=YYYYMMDD
    """
    params = {"dates": date_yyyymmdd}

    async with httpx.AsyncClient(timeout=25.0, headers={"User-Agent": "SportLytics/1.0"}) as client:
        r = await client.get(settings.ESPN_NBA_SCOREBOARD_URL, params=params)
        r.raise_for_status()
        return r.json()


def parse_espn_nba_scoreboard(payload: Dict[str, Any]) -> List[NBAGameRow]:
    events = payload.get("events") or []
    out: List[NBAGameRow] = []

    season_type = _map_season_type(payload)

    for ev in events:
        eid = str(ev.get("id") or "")
        if not eid:
            continue

        date = _parse_utc(ev.get("date"))
        season_year = (payload.get("season") or {}).get("year") or _infer_nba_season_year(date)

        comps = ev.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]

        competitors = comp.get("competitors") or []
        if len(competitors) < 2:
            continue

        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue

        home_team = ((home.get("team") or {}).get("abbreviation") or "").strip().upper()
        away_team = ((away.get("team") or {}).get("abbreviation") or "").strip().upper()
        if not home_team or not away_team:
            continue

        home_score = _to_int(home.get("score"))
        away_score = _to_int(away.get("score"))

        status, phase = _map_status(comp.get("status") or {})
        source_url = (ev.get("links") or [{}])[0].get("href") or "https://www.espn.com/nba/"

        out.append(
            NBAGameRow(
                eid=eid,
                season=int(season_year),
                season_type=season_type,
                game_date=date,
                home=home_team,
                away=away_team,
                home_score=home_score,
                away_score=away_score,
                status=status,
                phase=phase,
                source_url=source_url,
            )
        )

    return out
