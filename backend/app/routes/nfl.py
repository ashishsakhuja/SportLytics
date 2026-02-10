from __future__ import annotations

from datetime import date
from typing import Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Game, StandingsSnapshot, Team


router = APIRouter(prefix="/api/nfl", tags=["api:nfl"])


@router.get("/teams")
def list_teams(db: Session = Depends(get_db)):
    rows = (
        db.query(Team)
        .filter(Team.sport == "nfl")
        .order_by(Team.team_code.asc())
        .all()
    )
    return {
        "items": [
            {
                "team_code": t.team_code,
                "name": t.name,
                "city": t.city,
                "meta": t.meta,
            }
            for t in rows
        ]
    }


@router.get("/games")
def list_games(
    season: int = Query(..., description="Season year, e.g., 2024"),
    season_type: str = Query("REG", description="PRE | REG | POST"),
    week: Optional[int] = Query(None, ge=1, le=30),
    team: Optional[str] = Query(None, description="Filter by team code, e.g., PHI"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    season_type = season_type.upper().strip()

    q = (
        db.query(Game)
        .filter(
            Game.sport == "nfl",
            Game.season == season,
            Game.season_type == season_type,
        )
    )

    if week is not None:
        q = q.filter(Game.week == week)

    if team:
        team_code = team.upper().strip()
        q = q.filter(sa.or_(Game.home_team_code == team_code, Game.away_team_code == team_code))

    if date_from is not None:
        q = q.filter(Game.game_date >= sa.cast(date_from, sa.Date))

    if date_to is not None:
        # inclusive end date
        q = q.filter(Game.game_date < sa.cast(date_to, sa.Date) + sa.text("interval '1 day'"))

    rows = (
        q.order_by(Game.game_date.asc().nullslast(), Game.week.asc().nullslast(), Game.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "season": season,
        "season_type": season_type,
        "week": week,
        "team": team.upper().strip() if team else None,
        "count": len(rows),
        "items": [
            {
                "id": g.id,
                "week": g.week,
                "game_date": g.game_date.isoformat() + "Z" if g.game_date else None,
                "home_team": g.home_team_code,
                "away_team": g.away_team_code,
                "home_score": g.home_score,
                "away_score": g.away_score,
                "status": g.status,
                "source_url": g.source_url,
            }
            for g in rows
        ],
    }


@router.get("/standings/latest")
def latest_standings(
    season: int = Query(..., description="Season year, e.g., 2024"),
    season_type: str = Query("REG", description="PRE | REG | POST"),
    db: Session = Depends(get_db),
):
    season_type = season_type.upper().strip()

    latest_as_of = (
        db.query(sa.func.max(StandingsSnapshot.as_of))
        .filter(
            StandingsSnapshot.sport == "nfl",
            StandingsSnapshot.season == season,
            StandingsSnapshot.season_type == season_type,
        )
        .scalar()
    )

    if not latest_as_of:
        return {"as_of": None, "items": [], "source_url": "https://www.nfl.com/standings/"}

    rows = (
        db.query(StandingsSnapshot)
        .filter(
            StandingsSnapshot.sport == "nfl",
            StandingsSnapshot.season == season,
            StandingsSnapshot.season_type == season_type,
            StandingsSnapshot.as_of == latest_as_of,
        )
        .order_by(
            StandingsSnapshot.conference.asc().nullslast(),
            StandingsSnapshot.division.asc().nullslast(),
            StandingsSnapshot.rank.asc().nullslast(),
            StandingsSnapshot.team_code.asc(),
        )
        .all()
    )

    team_rows = (
        db.query(Team)
        .filter(Team.sport == "nfl", Team.team_code.in_([r.team_code for r in rows]))
        .all()
    )
    team_map = {t.team_code: t for t in team_rows}

    return {
        "as_of": latest_as_of.isoformat() + "Z",
        "source_url": rows[0].source_url if rows and rows[0].source_url else "https://www.nfl.com/standings/",
        "items": [
            {
                "team": r.team_code,
                "team_name": team_map.get(r.team_code).name if team_map.get(r.team_code) else None,
                "team_city": team_map.get(r.team_code).city if team_map.get(r.team_code) else None,
                "conference": r.conference,
                "division": r.division,
                "wins": r.wins,
                "losses": r.losses,
                "ties": r.ties,
                "pct": r.pct,
                "rank": r.rank,
            }
            for r in rows
        ],
    }
