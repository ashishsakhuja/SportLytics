from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

import httpx

from app.settings import settings


@dataclass(frozen=True)
class NFLGameRow:
    """Normalized game row parsed from the NFL scorestrip feed."""

    eid: str
    season: int
    season_type: str  # PRE | REG | POST
    week: int
    game_date: Optional[datetime]

    home: str
    away: str
    home_score: Optional[int]
    away_score: Optional[int]

    status: str  # pre | live | final
    phase: Optional[str]  # raw q value (P, F, 1, 2, H, OT, etc.)
    source_url: str


def _safe_int(x: Optional[str]) -> Optional[int]:
    if x is None:
        return None
    x = x.strip()
    if not x:
        return None
    try:
        return int(x)
    except ValueError:
        return None


def _parse_game_datetime(d: Optional[str], t: Optional[str]) -> Optional[datetime]:
    """Parse scorestrip date/time into a datetime.

    Note: scorestrip does not provide an explicit timezone.
    We store as a naive datetime; treat it consistently in the app.
    """
    if not d:
        return None
    d = d.strip()
    if not d:
        return None

    # date formats: 2018-09-06 or 20180906
    date_fmt = "%Y-%m-%d" if "-" in d else "%Y%m%d"

    if not t:
        try:
            return datetime.strptime(d, date_fmt)
        except ValueError:
            return None

    t = t.strip()
    if not t:
        try:
            return datetime.strptime(d, date_fmt)
        except ValueError:
            return None

    # common time format is HH:MM or H:MM
    for fmt in (f"{date_fmt} %H:%M", f"{date_fmt} %I:%M%p", f"{date_fmt} %I:%M %p"):
        try:
            return datetime.strptime(f"{d} {t}", fmt)
        except ValueError:
            continue
    return None


def _map_status(q: Optional[str]) -> Tuple[str, Optional[str]]:
    """Map scorestrip 'q' phase to a simple status."""
    if not q:
        return "pre", None
    q = q.strip().upper()

    if q in {"P", "PRE"}:
        return "pre", q
    if q.startswith("F"):
        return "final", q
    if q in {"H", "HT", "OT"}:
        return "live", q
    if q.isdigit():
        return "live", q

    return "pre", q


def parse_scorestrip_xml(
    xml_text: str,
    *,
    season: int,
    season_type: str,
    week: int,
) -> List[NFLGameRow]:
    """Transform NFL scorestrip XML -> normalized game rows."""

    season_type = season_type.upper()
    root = ET.fromstring(xml_text)

    out: List[NFLGameRow] = []
    for g in root.iter("g"):
        eid = g.attrib.get("eid") or g.attrib.get("id")
        if not eid:
            continue

        home = (g.attrib.get("h") or "").strip().upper()
        away = (g.attrib.get("v") or "").strip().upper()

        hs = _safe_int(g.attrib.get("hs"))
        vs = _safe_int(g.attrib.get("vs"))

        q = g.attrib.get("q")
        status, phase = _map_status(q)

        d = g.attrib.get("d")
        t = g.attrib.get("t")
        game_dt = _parse_game_datetime(d, t)

        # Link out: user can click to the NFL game page
        source_url = f"https://www.nfl.com/games/{eid}"

        out.append(
            NFLGameRow(
                eid=eid,
                season=season,
                season_type=season_type,
                week=week,
                game_date=game_dt,
                home=home,
                away=away,
                home_score=hs,
                away_score=vs,
                status=status,
                phase=phase,
                source_url=source_url,
            )
        )

    return out


async def fetch_scorestrip(season: int, season_type: str, week: int) -> str:
    """
    Fetch scorestrip XML for a given season_type/week.

    Primary: static.nfl.com/ajax/scorestrip?... (week-specific)
    Fallback: static.nfl.com/liveupdate/scorestrip/ss.xml (usually current week only)
    """
    season_type = season_type.upper().strip()

    primary_url = settings.NFL_SCORESTRIP_URL.format(
        season=season, season_type=season_type, week=week
    )

    async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "SportLytics/1.0"}) as client:
        r = await client.get(primary_url)
        if r.status_code == 200 and r.text:
            return r.text

        # If week-specific feed is gone, fall back to live feed (may not support historical weeks).
        # This is still useful for in-season live ingestion mode.
        fallback_url = getattr(settings, "NFL_SCORESTRIP_LIVE_URL", None)
        if fallback_url:
            r2 = await client.get(fallback_url)
            r2.raise_for_status()
            return r2.text

        r.raise_for_status()
        return r.text



async def fetch_gtd_json(eid: str) -> Dict[str, Any]:
    """Optional: fetch richer per-game JSON (drives/players/etc.)."""
    url = settings.NFL_GTD_URL.format(eid=eid)
    async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "SportLytics/1.0"}) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()
