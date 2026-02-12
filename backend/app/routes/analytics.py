from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Game

router = APIRouter(prefix="/analytics", tags=["analytics"])


SUPPORTED_DATA_SPORTS = {"nfl", "nba", "mlb", "nhl"}


def _norm_sport(s: str) -> str:
    s = (s or "").lower().strip()
    if s not in SUPPORTED_DATA_SPORTS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport '{s}'. Supported: {sorted(SUPPORTED_DATA_SPORTS)}")
    return s


@router.get("/games/recent")
def recent_games(
    sport: str = Query(..., description="nfl/nba/mlb/nhl"),
    days: int = Query(7, ge=1, le=60),
    db: Session = Depends(get_db),
):
    """
    Recent games (chart/table-ready). Uses game_date and status.
    """
    sport = _norm_sport(sport)
    since = datetime.utcnow() - timedelta(days=days)

    rows = (
        db.query(Game)
        .filter(
            Game.sport == sport,
            Game.game_date.isnot(None),
            Game.game_date >= since,
        )
        .order_by(Game.game_date.desc())
        .limit(5000)
        .all()
    )

    return {
        "sport": sport,
        "since": since.isoformat() + "Z",
        "count": len(rows),
        "games": [
            {
                "game_date": g.game_date.isoformat() + "Z" if g.game_date else None,
                "home": g.home_team_code,
                "away": g.away_team_code,
                "home_score": g.home_score,
                "away_score": g.away_score,
                "status": g.status,
                "season": g.season,
                "season_type": g.season_type,
                "provider": g.provider,
                "external_game_id": g.external_game_id,
                "source_url": g.source_url,
            }
            for g in rows
        ],
    }


@router.get("/games/upcoming")
def upcoming_games(
    sport: str = Query(..., description="nfl/nba/mlb/nhl"),
    days: int = Query(7, ge=1, le=60),
    db: Session = Depends(get_db),
):
    """
    Upcoming games in next N days (chart/table-ready).
    """
    sport = _norm_sport(sport)
    now = datetime.utcnow()
    until = now + timedelta(days=days)

    rows = (
        db.query(Game)
        .filter(
            Game.sport == sport,
            Game.game_date.isnot(None),
            Game.game_date >= now,
            Game.game_date <= until,
        )
        .order_by(Game.game_date.asc())
        .limit(5000)
        .all()
    )

    return {
        "sport": sport,
        "from": now.isoformat() + "Z",
        "to": until.isoformat() + "Z",
        "count": len(rows),
        "games": [
            {
                "game_date": g.game_date.isoformat() + "Z" if g.game_date else None,
                "home": g.home_team_code,
                "away": g.away_team_code,
                "status": g.status,
                "season": g.season,
                "season_type": g.season_type,
                "source_url": g.source_url,
            }
            for g in rows
        ],
    }


@router.get("/teams/{sport}/{team_code}/form")
def team_form(
    sport: str,
    team_code: str,
    season: int = Query(...),
    season_type: str = Query("REG"),
    last: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Chart-ready arrays for a team's last N games:
    dates, opponents, home_away, score_for, score_against, margin, result
    Works across nfl/nba/mlb/nhl (score meaning differs: points/runs/goals).
    """
    sport = _norm_sport(sport)
    team_code = team_code.upper().strip()
    season_type = season_type.upper().strip()

    games = (
        db.query(Game)
        .filter(
            Game.sport == sport,
            Game.season == season,
            Game.season_type == season_type,
            sa.or_(Game.home_team_code == team_code, Game.away_team_code == team_code),
            Game.game_date.isnot(None),
        )
        .order_by(Game.game_date.desc())
        .limit(last)
        .all()
    )

    if not games:
        raise HTTPException(status_code=404, detail="No games found for team/season.")

    games = list(reversed(games))  # oldest -> newest

    dates = []
    opponents = []
    home_away = []
    score_for = []
    score_against = []
    margin = []
    results = []
    source_urls = []

    for g in games:
        is_home = g.home_team_code == team_code
        opp = g.away_team_code if is_home else g.home_team_code

        sf = g.home_score if is_home else g.away_score
        sa_ = g.away_score if is_home else g.home_score

        dates.append(g.game_date.date().isoformat() if g.game_date else None)
        opponents.append(opp)
        home_away.append("home" if is_home else "away")
        score_for.append(sf)
        score_against.append(sa_)

        if sf is not None and sa_ is not None:
            margin.append(sf - sa_)
            results.append("W" if sf > sa_ else ("L" if sf < sa_ else "T"))
        else:
            margin.append(None)
            results.append(None)

        source_urls.append(g.source_url)

    return {
        "sport": sport,
        "team": team_code,
        "season": season,
        "season_type": season_type,
        "last": last,
        "dates": dates,
        "opponents": opponents,
        "home_away": home_away,
        "score_for": score_for,
        "score_against": score_against,
        "margin": margin,
        "results": results,
        "source_urls": source_urls,
    }


@router.get("/league/{sport}/scoring/timeseries")
def league_scoring_timeseries(
    sport: str,
    start: date = Query(..., description="YYYY-MM-DD"),
    end: date = Query(..., description="YYYY-MM-DD"),
    bucket: Literal["day", "week"] = Query("day"),
    db: Session = Depends(get_db),
):
    """
    League-wide average total score per game over time (chart-ready).
    """
    sport = _norm_sport(sport)
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")

    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time())  # inclusive end date

    trunc_unit = "day" if bucket == "day" else "week"
    bucket_expr = sa.func.date_trunc(trunc_unit, Game.game_date).label("bucket")

    total_score = (sa.func.coalesce(Game.home_score, 0) + sa.func.coalesce(Game.away_score, 0)).label("total_score")

    rows = (
        db.query(
            bucket_expr,
            sa.func.count(Game.id).label("games"),
            sa.func.avg(total_score).label("avg_total_score"),
        )
        .filter(
            Game.sport == sport,
            Game.game_date.isnot(None),
            Game.game_date >= start_dt,
            Game.game_date < end_dt,
        )
        .group_by(bucket_expr)
        .order_by(bucket_expr.asc())
        .all()
    )

    return {
        "sport": sport,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "bucket": bucket,
        "points_label": {"nfl": "points", "nba": "points", "mlb": "runs", "nhl": "goals"}[sport],
        "x": [r.bucket.date().isoformat() if r.bucket else None for r in rows],
        "games": [int(r.games) for r in rows],
        "avg_total_score": [float(r.avg_total_score) if r.avg_total_score is not None else None for r in rows],
    }
