from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Game, Team

router = APIRouter(prefix="/analytics", tags=["analytics"])

SUPPORTED_DATA_SPORTS = {"nfl", "nba", "mlb", "nhl"}
POINTS_LABEL = {"nfl": "points", "nba": "points", "mlb": "runs", "nhl": "goals"}


def _norm_sport(s: str) -> str:
    s = (s or "").lower().strip()
    if s not in SUPPORTED_DATA_SPORTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported sport '{s}'. Supported: {sorted(SUPPORTED_DATA_SPORTS)}",
        )
    return s




def _canonical_team_code(sport: str, code: str) -> str:
    c = (code or "").upper().strip()
    if sport == "nfl":
        return {"WSH": "WAS"}.get(c, c)
    return c


def _team_code_variants(sport: str, code: str) -> list[str]:
    c = _canonical_team_code(sport, code)
    if sport == "nfl" and c == "WAS":
        return ["WAS", "WSH"]
    return [c]

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


@router.get("/teams")
def list_teams(
    sport: str = Query(..., description="nfl/nba/mlb/nhl"),
    db: Session = Depends(get_db),
):
    sport = _norm_sport(sport)
    rows = (
        db.query(Team)
        .filter(Team.sport == sport)
        .order_by(Team.team_code.asc())
        .all()
    )

    deduped: dict[str, Team] = {}
    for t in rows:
        canonical = _canonical_team_code(sport, t.team_code)
        existing = deduped.get(canonical)
        if existing is None:
            deduped[canonical] = t
            continue
        existing_score = 0 if existing.name == existing.team_code else 1
        current_score = 0 if t.name == t.team_code else 1
        if current_score > existing_score:
            deduped[canonical] = t

    teams = [
        {
            "team_code": canonical,
            "name": (t.name if t.name and t.name != t.team_code else canonical),
            "city": t.city,
            "meta": t.meta,
        }
        for canonical, t in sorted(deduped.items(), key=lambda item: item[0])
    ]

    return {
        "sport": sport,
        "count": len(teams),
        "teams": teams,
    }


@router.get("/games/recent")
def recent_games(
    sport: str = Query(..., description="nfl/nba/mlb/nhl"),
    days: int = Query(7, ge=1, le=60),
    db: Session = Depends(get_db),
):
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


@router.get("/league/{sport}/standings")
def league_standings(
    sport: str,
    season: int = Query(...),
    season_type: str = Query("REG", description="REG/PRE/POST"),
    db: Session = Depends(get_db),
):
    """
    Generic standings derived from game results (works for nfl/nba/mlb/nhl).
    Returns chart/table-ready rows: W/L/T, GP, PF/PA, win_pct.
    """
    sport = _norm_sport(sport)
    season_type = (season_type or "").upper().strip()

    g = Game.__table__

    # Two perspectives: one row for home team, one for away team
    home_rows = sa.select(
        g.c.home_team_code.label("team_code"),
        sa.literal(1).label("gp"),
        sa.case((g.c.home_score > g.c.away_score, 1), else_=0).label("w"),
        sa.case((g.c.home_score < g.c.away_score, 1), else_=0).label("l"),
        sa.case((g.c.home_score == g.c.away_score, 1), else_=0).label("t"),
        g.c.home_score.label("pf"),
        g.c.away_score.label("pa"),
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
        g.c.away_score.label("pf"),
        g.c.home_score.label("pa"),
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
            sa.func.sum(unioned.c.pf).label("pf"),
            sa.func.sum(unioned.c.pa).label("pa"),
        )
        .group_by(unioned.c.team_code)
        .subquery("standings")
    )

    # join team names if present
    t = Team.__table__
    q = (
        sa.select(
            agg.c.team_code,
            t.c.name,
            t.c.city,
            agg.c.gp,
            agg.c.w,
            agg.c.l,
            agg.c.t,
            agg.c.pf,
            agg.c.pa,
            (agg.c.pf - agg.c.pa).label("diff"),
        )
        .select_from(
            agg.outerjoin(
                t,
                sa.and_(t.c.sport == sport, t.c.team_code == agg.c.team_code),
            )
        )
    )

    rows = db.execute(q).mappings().all()

    out = []
    for r in rows:
        gp = int(r["gp"] or 0)
        w = int(r["w"] or 0)
        l = int(r["l"] or 0)
        t_ = int(r["t"] or 0)
        win_pct = (w + 0.5 * t_) / gp if gp else 0.0
        out.append(
            {
                "team_code": r["team_code"],
                "name": r["name"],
                "city": r["city"],
                "gp": gp,
                "w": w,
                "l": l,
                "t": t_,
                "pf": int(r["pf"] or 0),
                "pa": int(r["pa"] or 0),
                "diff": int(r["diff"] or 0),
                "win_pct": round(float(win_pct), 4),
            }
        )

    out.sort(key=lambda x: (x["win_pct"], x["diff"], x["pf"]), reverse=True)

    return {
        "sport": sport,
        "season": season,
        "season_type": season_type,
        "points_label": POINTS_LABEL[sport],
        "count": len(out),
        "standings": out,
    }


@router.get("/league/{sport}/team-summary")
def league_team_summary(
    sport: str,
    season: int = Query(...),
    season_type: str = Query("REG"),
    db: Session = Depends(get_db),
):
    """
    Team-level summary table (great for dashboards):
    GP, avg PF, avg PA, avg margin, total PF/PA.
    """
    sport = _norm_sport(sport)
    season_type = (season_type or "").upper().strip()

    g = Game.__table__

    home_rows = sa.select(
        g.c.home_team_code.label("team_code"),
        sa.literal(1).label("gp"),
        g.c.home_score.label("pf"),
        g.c.away_score.label("pa"),
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
        g.c.away_score.label("pf"),
        g.c.home_score.label("pa"),
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
            sa.func.sum(unioned.c.pf).label("pf"),
            sa.func.sum(unioned.c.pa).label("pa"),
            sa.func.avg((unioned.c.pf - unioned.c.pa)).label("avg_margin"),
            sa.func.avg(unioned.c.pf).label("avg_pf"),
            sa.func.avg(unioned.c.pa).label("avg_pa"),
        )
        .group_by(unioned.c.team_code)
        .subquery("summary")
    )

    t = Team.__table__
    q = sa.select(
        agg.c.team_code,
        t.c.name,
        t.c.city,
        agg.c.gp,
        agg.c.pf,
        agg.c.pa,
        agg.c.avg_pf,
        agg.c.avg_pa,
        agg.c.avg_margin,
    ).select_from(
        agg.outerjoin(t, sa.and_(t.c.sport == sport, t.c.team_code == agg.c.team_code))
    )

    rows = db.execute(q).mappings().all()

    out = []
    for r in rows:
        out.append(
            {
                "team_code": r["team_code"],
                "name": r["name"],
                "city": r["city"],
                "gp": int(r["gp"] or 0),
                "pf": int(r["pf"] or 0),
                "pa": int(r["pa"] or 0),
                "avg_pf": float(r["avg_pf"]) if r["avg_pf"] is not None else None,
                "avg_pa": float(r["avg_pa"]) if r["avg_pa"] is not None else None,
                "avg_margin": float(r["avg_margin"]) if r["avg_margin"] is not None else None,
            }
        )

    out.sort(key=lambda x: (x["avg_margin"] is not None, x["avg_margin"]), reverse=True)

    return {
        "sport": sport,
        "season": season,
        "season_type": season_type,
        "points_label": POINTS_LABEL[sport],
        "count": len(out),
        "teams": out,
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
    """
    sport = _norm_sport(sport)
    team_code = _canonical_team_code(sport, team_code)
    team_variants = _team_code_variants(sport, team_code)
    season_type = season_type.upper().strip()

    games = (
        db.query(Game)
        .filter(
            Game.sport == sport,
            Game.season == season,
            Game.season_type == season_type,
            sa.or_(Game.home_team_code.in_(team_variants), Game.away_team_code.in_(team_variants)),
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
        is_home = (g.home_team_code or "").upper() in team_variants
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


@router.get("/teams/{sport}/{team_code}/splits/home-away")
def team_splits_home_away(
    sport: str,
    team_code: str,
    season: int = Query(...),
    season_type: str = Query("REG"),
    db: Session = Depends(get_db),
):
    """
    Home vs Away splits for dashboards:
    GP/W/L/T + avg PF/PA/margin for home and away.
    """
    sport = _norm_sport(sport)
    team_code = _canonical_team_code(sport, team_code)
    team_variants = _team_code_variants(sport, team_code)
    season_type = season_type.upper().strip()

    games = (
        db.query(Game)
        .filter(
            Game.sport == sport,
            Game.season == season,
            Game.season_type == season_type,
            sa.or_(Game.home_team_code.in_(team_variants), Game.away_team_code.in_(team_variants)),
            Game.game_date.isnot(None),
            _finalish_filter(),
        )
        .order_by(Game.game_date.asc())
        .all()
    )

    def _bucket(is_home: bool):
        bucket_games = [g for g in games if (((g.home_team_code or "").upper() in team_variants) == is_home)]
        gp = len(bucket_games)
        w = l = t_ = 0
        pf = pa = 0
        for g in bucket_games:
            sf = g.home_score if is_home else g.away_score
            sa_ = g.away_score if is_home else g.home_score
            if sf is None or sa_ is None:
                continue
            pf += int(sf)
            pa += int(sa_)
            if sf > sa_:
                w += 1
            elif sf < sa_:
                l += 1
            else:
                t_ += 1
        avg_pf = (pf / gp) if gp else None
        avg_pa = (pa / gp) if gp else None
        avg_margin = ((pf - pa) / gp) if gp else None
        return {
            "gp": gp,
            "w": w,
            "l": l,
            "t": t_,
            "pf": pf,
            "pa": pa,
            "avg_pf": avg_pf,
            "avg_pa": avg_pa,
            "avg_margin": avg_margin,
        }

    return {
        "sport": sport,
        "team": team_code,
        "season": season,
        "season_type": season_type,
        "points_label": POINTS_LABEL[sport],
        "home": _bucket(True),
        "away": _bucket(False),
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
            _finalish_filter(),
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
        "points_label": POINTS_LABEL[sport],
        "x": [r.bucket.date().isoformat() if r.bucket else None for r in rows],
        "games": [int(r.games) for r in rows],
        "avg_total_score": [float(r.avg_total_score) if r.avg_total_score is not None else None for r in rows],
    }


@router.get("/league/{sport}/scoring/distribution")
def league_scoring_distribution(
    sport: str,
    season: int = Query(...),
    season_type: str = Query("REG"),
    bins: int = Query(12, ge=5, le=40),
    db: Session = Depends(get_db),
):
    """
    Histogram-ready distribution of total score per game for a season.
    Returns bins + counts (UI can render bar chart).
    """
    sport = _norm_sport(sport)
    season_type = (season_type or "").upper().strip()

    totals = (
        db.query((Game.home_score + Game.away_score).label("total"))
        .filter(
            Game.sport == sport,
            Game.season == season,
            Game.season_type == season_type,
            Game.game_date.isnot(None),
            _finalish_filter(),
        )
        .all()
    )

    vals = [int(r.total) for r in totals if r.total is not None]
    if not vals:
        return {
            "sport": sport,
            "season": season,
            "season_type": season_type,
            "points_label": POINTS_LABEL[sport],
            "bins": [],
            "counts": [],
            "min": None,
            "max": None,
            "n": 0,
        }

    vmin, vmax = min(vals), max(vals)
    if vmin == vmax:
        return {
            "sport": sport,
            "season": season,
            "season_type": season_type,
            "points_label": POINTS_LABEL[sport],
            "bins": [vmin],
            "counts": [len(vals)],
            "min": vmin,
            "max": vmax,
            "n": len(vals),
        }

    # build equal-width bins
    width = (vmax - vmin) / bins
    edges = [vmin + i * width for i in range(bins + 1)]
    counts = [0] * bins

    for x in vals:
        idx = int((x - vmin) / width)
        if idx == bins:
            idx = bins - 1
        counts[idx] += 1

    # return labels as "lo-hi"
    labels = []
    for i in range(bins):
        lo = int(round(edges[i]))
        hi = int(round(edges[i + 1]))
        if i == bins - 1:
            hi = vmax
        labels.append(f"{lo}-{hi}")

    return {
        "sport": sport,
        "season": season,
        "season_type": season_type,
        "points_label": POINTS_LABEL[sport],
        "bins": labels,
        "counts": counts,
        "min": vmin,
        "max": vmax,
        "n": len(vals),
    }
