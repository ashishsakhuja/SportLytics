from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

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
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported sport '{s}'. Supported: {sorted(SUPPORTED_DATA_SPORTS)}",
        )
    return s


def _finalish_filter():
    """
    ESPN providers typically use: pre / in / final
    Use BOTH status == 'final' and 'scores not null' so it works across providers.
    """
    return sa.and_(
        Game.home_score.isnot(None),
        Game.away_score.isnot(None),
        sa.or_(Game.status == "final", Game.status.is_(None)),
    )


def _standings_win_pct_map(
    db: Session, sport: str, season: int, season_type: str
) -> Dict[str, float]:
    """
    Compute win_pct per team from games table (same logic as standings endpoint),
    but returned as a dict {team_code: win_pct}.
    """
    g = Game.__table__

    home_rows = sa.select(
        g.c.home_team_code.label("team_code"),
        sa.literal(1).label("gp"),
        sa.case((g.c.home_score > g.c.away_score, 1), else_=0).label("w"),
        sa.case((g.c.home_score < g.c.away_score, 1), else_=0).label("l"),
        sa.case((g.c.home_score == g.c.away_score, 1), else_=0).label("t"),
    ).where(
        sa.and_(
            g.c.sport == sport,
            g.c.season == season,
            g.c.season_type == season_type,
            g.c.game_date.isnot(None),
            _finalish_filter(),
        )
    )

    away_rows = sa.select(
        g.c.away_team_code.label("team_code"),
        sa.literal(1).label("gp"),
        sa.case((g.c.away_score > g.c.home_score, 1), else_=0).label("w"),
        sa.case((g.c.away_score < g.c.home_score, 1), else_=0).label("l"),
        sa.case((g.c.away_score == g.c.home_score, 1), else_=0).label("t"),
    ).where(
        sa.and_(
            g.c.sport == sport,
            g.c.season == season,
            g.c.season_type == season_type,
            g.c.game_date.isnot(None),
            _finalish_filter(),
        )
    )

    unioned = sa.union_all(home_rows, away_rows).subquery("team_games")

    agg = (
        sa.select(
            unioned.c.team_code,
            sa.func.sum(unioned.c.gp).label("gp"),
            sa.func.sum(unioned.c.w).label("w"),
            sa.func.sum(unioned.c.l).label("l"),
            sa.func.sum(unioned.c.t).label("t"),
        )
        .group_by(unioned.c.team_code)
        .subquery("standings")
    )

    rows = db.execute(sa.select(agg)).mappings().all()

    out: Dict[str, float] = {}
    for r in rows:
        gp = int(r["gp"] or 0)
        w = int(r["w"] or 0)
        t_ = int(r["t"] or 0)
        win_pct = (w + 0.5 * t_) / gp if gp else 0.0
        out[str(r["team_code"]).upper()] = float(round(win_pct, 6))
    return out


@router.get("/teams/{sport}/{team_code}/sos")
def team_strength_of_schedule(
    sport: str,
    team_code: str,
    season: int = Query(...),
    season_type: str = Query("REG", description="REG/POST"),
    last: int = Query(50, ge=1, le=200, description="Max games to return (ordered oldest->newest)"),
    db: Session = Depends(get_db),
):
    """
    True SOS (Strength of Schedule) using opponent win% (same season + season_type).
    Returns chart-ready rows per game:
      - opponent win%
      - cumulative SOS (avg opp win% so far)
      - rolling SOS (avg opp win% last N games)
    """
    sport = _norm_sport(sport)
    team_code = (team_code or "").upper().strip()
    season_type = (season_type or "").upper().strip()
    if season_type not in {"REG", "POST"}:
        raise HTTPException(status_code=400, detail="season_type must be REG or POST")

    games = (
        db.query(Game)
        .filter(
            Game.sport == sport,
            Game.season == season,
            Game.season_type == season_type,
            sa.or_(Game.home_team_code == team_code, Game.away_team_code == team_code),
            Game.game_date.isnot(None),
            _finalish_filter(),
        )
        .order_by(Game.game_date.asc())
        .limit(last)
        .all()
    )

    if not games:
        raise HTTPException(status_code=404, detail="No games found for team/season.")

    win_pct_map = _standings_win_pct_map(db, sport, season, season_type)

    rows: List[dict] = []
    opp_wps: List[float] = []
    roll_window = 5

    for i, g in enumerate(games, start=1):
        is_home = (g.home_team_code or "").upper() == team_code
        opp = (g.away_team_code if is_home else g.home_team_code) or ""
        opp = opp.upper()

        sf = g.home_score if is_home else g.away_score
        sa_ = g.away_score if is_home else g.home_score

        result: Optional[str] = None
        if sf is not None and sa_ is not None:
            if sf > sa_:
                result = "W"
            elif sf < sa_:
                result = "L"
            else:
                result = "T"

        opp_wp = float(win_pct_map.get(opp, 0.0))
        opp_wps.append(opp_wp)

        cum_avg = sum(opp_wps) / len(opp_wps) if opp_wps else 0.0
        roll_slice = opp_wps[max(0, len(opp_wps) - roll_window) :]
        roll_avg = sum(roll_slice) / len(roll_slice) if roll_slice else 0.0

        rows.append(
            {
                "idx": i,
                "date": g.game_date.date().isoformat() if g.game_date else None,
                "opponent": opp,
                "home_away": "home" if is_home else "away",
                "result": result,
                "opp_win_pct": round(opp_wp, 6),
                "sos_cum": round(float(cum_avg), 6),
                "sos_roll5": round(float(roll_avg), 6),
            }
        )

    sos_avg = sum(opp_wps) / len(opp_wps) if opp_wps else 0.0

    return {
        "sport": sport,
        "team": team_code,
        "season": season,
        "season_type": season_type,
        "games": len(rows),
        "roll_window": roll_window,
        "sos_avg": round(float(sos_avg), 6),
        "rows": rows,
    }