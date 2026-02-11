from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.settings import settings


@dataclass(frozen=True)
class MLBGameRow:
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


def _map_status(status_obj: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """
    ESPN usually gives:
      status.type.state: 'pre' | 'in' | 'post'
      status.type.completed: bool
      status.type.detail: 'Final', 'Top 5th', 'Wed, ...', etc.
    """
    t = (status_obj.get("type") or {})
    state = (t.get("state") or "").lower()
    completed = t.get("completed")
    detail = t.get("detail")

    if completed is True or state == "post":
        return "final", detail
    if state == "in":
        return "live", detail
    return "pre", detail


def _map_season_type(payload: Dict[str, Any]) -> str:
    # ESPN season.type often: 1=pre, 2=reg, 3=post
    st = (payload.get("season") or {}).get("type")
    if st == 1:
        return "PRE"
    if st == 3:
        return "POST"
    return "REG"


import asyncio
import httpx

async def fetch_espn_mlb_scoreboard(*, date_yyyymmdd: str) -> Dict[str, Any]:
    params = {"dates": date_yyyymmdd}

    delays = [1.0, 2.0, 4.0]  # exponential-ish backoff
    last_err: Exception | None = None

    async with httpx.AsyncClient(timeout=25.0, headers={"User-Agent": "SportLytics/1.0"}) as client:
        for attempt in range(len(delays) + 1):
            try:
                r = await client.get(settings.ESPN_MLB_SCOREBOARD_URL, params=params)
                r.raise_for_status()
                return r.json()
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as e:
                last_err = e

                status = None
                if isinstance(e, httpx.HTTPStatusError):
                    status = e.response.status_code

                # retry on transient server/client throttling
                if status in (429, 500, 502, 503, 504) or status is None:
                    if attempt < len(delays):
                        await asyncio.sleep(delays[attempt])
                        continue

                raise

    # should never hit
    raise last_err or RuntimeError("fetch failed")



def parse_espn_mlb_scoreboard(payload: Dict[str, Any]) -> List[MLBGameRow]:
    events = payload.get("events") or []
    out: List[MLBGameRow] = []

    season_type = _map_season_type(payload)

    for ev in events:
        eid = str(ev.get("id") or "")
        if not eid:
            continue

        date = _parse_utc(ev.get("date"))
        season_year = (payload.get("season") or {}).get("year") or (date.year if date else datetime.utcnow().year)

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
        source_url = (ev.get("links") or [{}])[0].get("href") or "https://www.espn.com/mlb/"

        out.append(
            MLBGameRow(
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
