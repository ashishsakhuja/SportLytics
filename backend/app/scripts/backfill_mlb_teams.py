from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.db import SessionLocal
from app.models import Team
from app.settings import settings


def _iter_team_blobs(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    sports = payload.get("sports") or []
    out: List[Dict[str, Any]] = []
    for s in sports:
        for lg in (s.get("leagues") or []):
            for t in (lg.get("teams") or []):
                team = t.get("team") or {}
                if team:
                    out.append(team)
    if not out and isinstance(payload.get("teams"), list):
        for t in payload["teams"]:
            team = (t or {}).get("team") or t
            if isinstance(team, dict):
                out.append(team)
    return out


def _parse_team(team: Dict[str, Any]) -> Optional[Tuple[str, str, Optional[str]]]:
    abbr = (team.get("abbreviation") or "").strip().upper()
    if not abbr:
        return None

    location = (team.get("location") or "").strip()
    name_only = (team.get("name") or "").strip()
    display = (team.get("displayName") or "").strip()

    if location and name_only:
        full_name = f"{location} {name_only}".strip()
    elif display:
        full_name = display
    else:
        full_name = abbr

    city = location or None
    return abbr, full_name, city


async def fetch_espn_mlb_teams() -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=25.0, headers={"User-Agent": "SportLytics/1.0"}) as client:
        r = await client.get(settings.ESPN_MLB_TEAMS_URL)
        r.raise_for_status()
        return r.json()


async def main_async() -> None:
    payload = await fetch_espn_mlb_teams()
    teams = _iter_team_blobs(payload)

    db = SessionLocal()
    try:
        upserted = 0
        for t in teams:
            parsed = _parse_team(t)
            if not parsed:
                continue
            code, full_name, city = parsed

            existing = db.query(Team).filter(Team.sport == "mlb", Team.team_code == code).one_or_none()
            if existing:
                existing.name = full_name
                existing.city = city
            else:
                db.add(Team(sport="mlb", team_code=code, name=full_name, city=city, meta=None))
            upserted += 1

        db.commit()
        print(f"[MLB] backfill teams upserted={upserted}")
    finally:
        db.close()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
