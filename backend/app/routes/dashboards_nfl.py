from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import sqlalchemy as sa

from app.db import get_db
from app.models import Game, StandingsSnapshot


router = APIRouter(prefix="/dashboards/nfl", tags=["dashboards:nfl"])


@router.get("/standings")
def get_standings(
    season: int = Query(...),
    season_type: str = Query("REG"),
    db: Session = Depends(get_db),
):
    """Return the latest standings snapshot for the requested season."""

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

    return {
        "as_of": latest_as_of.isoformat() + "Z",
        "source_url": rows[0].source_url if rows and rows[0].source_url else "https://www.nfl.com/standings/",
        "items": [
            {
                "team": r.team_code,
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


@router.get("/teams/{team_code}/form")
def team_form(
    team_code: str,
    season: int = Query(...),
    season_type: str = Query("REG"),
    last: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Return chart-ready arrays for a team's last N games in the given season."""

    team_code = team_code.upper().strip()
    season_type = season_type.upper().strip()

    games = (
        db.query(Game)
        .filter(
            Game.sport == "nfl",
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
    points_for = []
    points_against = []
    margin = []
    results = []
    opponents = []
    home_away = []
    source_urls = []

    for g in games:
        is_home = g.home_team_code == team_code
        opp = g.away_team_code if is_home else g.home_team_code

        pf = g.home_score if is_home else g.away_score
        pa = g.away_score if is_home else g.home_score

        dates.append(g.game_date.date().isoformat() if g.game_date else None)
        opponents.append(opp)
        home_away.append("home" if is_home else "away")
        points_for.append(pf)
        points_against.append(pa)

        if pf is not None and pa is not None:
            margin.append(pf - pa)
            results.append("W" if pf > pa else ("L" if pf < pa else "T"))
        else:
            margin.append(None)
            results.append(None)

        source_urls.append(g.source_url)

    return {
        "team": team_code,
        "season": season,
        "season_type": season_type,
        "last": last,
        "dates": dates,
        "opponents": opponents,
        "home_away": home_away,
        "points_for": points_for,
        "points_against": points_against,
        "margin": margin,
        "results": results,
        "source_urls": source_urls,
    }
