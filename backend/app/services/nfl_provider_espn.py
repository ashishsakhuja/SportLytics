from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.settings import settings


@dataclass(frozen=True)
class NFLGameRow:
    eid: str
    season: int
    season_type: str  # "REG" | "POST" | "PRE"
    week: int
    game_date: Optional[datetime]

    home: str
    away: str
    home_score: Optional[int]
    away_score: Optional[int]

    status: str  # pre | live | final
    phase: Optional[str]
    source_url: str


# ESPN -> your team codes (ESPN uses standard abbreviations already)
# But include normalization in case.
_TEAM_CODE_NORMALIZE = {
    "JAC": "JAX",
    "WSH": "WAS",
}


def _norm(code: str) -> str:
    c = (code or "").strip().upper()
    return _TEAM_CODE_NORMALIZE.get(c, c)


def _parse_utc(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    # ESPN uses ISO 8601 like "2024-09-08T17:00Z"
    try:
        # handle Z
        if dt_str.endswith("Z"):
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(dt_str)
        # store naive UTC for consistency with your DB (or keep aware; your model uses DateTime without tz)
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


def _map_status(espn_status: Dict[str, Any]) -> tuple[str, Optional[str]]:
    """
    ESPN: status.type.name / state / completed
    """
    st = (espn_status.get("type") or {}).get("state") or ""
    completed = (espn_status.get("type") or {}).get("completed")
    detail = (espn_status.get("type") or {}).get("detail")  # "Final", "Q3 10:22", etc.

    if completed is True:
        return "final", detail
    if st == "in":
        return "live", detail
    return "pre", detail


async def fetch_espn_scoreboard(*, week: int, season: int, season_type: str) -> Dict[str, Any]:
    """
    ESPN scoreboard supports: ?seasontype=2&week=1&year=2024
    seasontype: 1=pre, 2=reg, 3=post
    """
    st_map = {"PRE": 1, "REG": 2, "POST": 3}
    seasontype_num = st_map.get(season_type.upper().strip(), 2)

    params = {"week": week, "year": season, "seasontype": seasontype_num}

    async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "SportLytics/1.0"}) as client:
        r = await client.get(settings.ESPN_NFL_SCOREBOARD_URL, params=params)
        r.raise_for_status()
        return r.json()


def parse_espn_scoreboard(
    payload: Dict[str, Any],
    *,
    season: int,
    season_type: str,
    week: int,
) -> List[NFLGameRow]:
    events = payload.get("events") or []
    out: List[NFLGameRow] = []

    for ev in events:
        raw_id = str(ev.get("id") or "")
        eid = f"{season}-{raw_id}"

        if not eid:
            continue

        date = _parse_utc(ev.get("date"))
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

        home_team = _norm(((home.get("team") or {}).get("abbreviation") or ""))
        away_team = _norm(((away.get("team") or {}).get("abbreviation") or ""))

        # scores arrive as strings sometimes
        def _to_int(x: Any) -> Optional[int]:
            try:
                if x is None:
                    return None
                return int(x)
            except Exception:
                return None

        home_score = _to_int(home.get("score"))
        away_score = _to_int(away.get("score"))

        status, phase = _map_status(comp.get("status") or {})
        source_url = (ev.get("links") or [{}])[0].get("href") or "https://www.espn.com/nfl/"

        out.append(
            NFLGameRow(
                eid=eid,
                season=season,
                season_type=season_type.upper().strip(),
                week=week,
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
