from __future__ import annotations

from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Game, TeamGameStats


router = APIRouter(prefix="/analytics", tags=["analytics"])


def _finalish_filter():
    return sa.and_(
        Game.home_score.isnot(None),
        Game.away_score.isnot(None),
        sa.or_(Game.status == "final", Game.status.is_(None)),
    )


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)

    s = str(v).strip()
    if not s:
        return None
    if s.endswith("%"):
        s = s[:-1].strip()
    try:
        return float(s)
    except Exception:
        return None


def _to_int(v: Any) -> Optional[int]:
    f = _to_float(v)
    if f is None:
        return None
    try:
        return int(round(f))
    except Exception:
        return None


@router.get("/nhl/teams/{team_code}/in-game/summary")
def nhl_in_game_summary(
    team_code: str,
    season: int = Query(...),
    season_type: str = Query("REG", description="REG/POST"),
    last: int = Query(82, ge=5, le=200, description="Max games to return (oldest->newest)"),
    roll: int = Query(5, ge=2, le=20, description="Rolling window size"),
    db: Session = Depends(get_db),
):
    sport = "nhl"
    team_code = (team_code or "").upper().strip()
    season_type = (season_type or "").upper().strip()

    if season_type not in {"REG", "POST"}:
        raise HTTPException(status_code=400, detail="season_type must be REG or POST")

    rows = (
        db.query(Game, TeamGameStats)
        .join(TeamGameStats, TeamGameStats.game_id == Game.id)
        .filter(
            Game.sport == sport,
            Game.season == season,
            Game.season_type == season_type,
            _finalish_filter(),
            TeamGameStats.team_code == team_code,
        )
        .order_by(Game.game_date.desc().nullslast(), Game.id.desc())
        .limit(last)
        .all()
    )

    if not rows:
        raise HTTPException(status_code=404, detail="No in-game stats found for this team/season.")

    rows = list(reversed(rows))  # oldest -> newest

    out_rows: List[Dict[str, Any]] = []

    def roll_mean(vals: List[Optional[float]], i: int) -> Optional[float]:
        w = []
        for j in range(max(0, i - roll + 1), i + 1):
            if vals[j] is not None:
                w.append(float(vals[j]))
        if not w:
            return None
        return sum(w) / len(w)

    shots_vals: List[Optional[float]] = []
    hits_vals: List[Optional[float]] = []
    blocks_vals: List[Optional[float]] = []
    faceoff_vals: List[Optional[float]] = []
    giveaways_vals: List[Optional[float]] = []
    takeaways_vals: List[Optional[float]] = []
    pp_pct_vals: List[Optional[float]] = []
    shooting_pct_vals: List[Optional[float]] = []
    pim_vals: List[Optional[float]] = []

    for idx, (g, tgs) in enumerate(rows, start=1):
        is_home = (g.home_team_code or "").upper() == team_code
        opp = (g.away_team_code if is_home else g.home_team_code) or ""

        pf = g.home_score if is_home else g.away_score
        pa = g.away_score if is_home else g.home_score
        margin = (pf - pa) if (pf is not None and pa is not None) else None

        result: Optional[str] = None
        if pf is not None and pa is not None:
            if pf > pa:
                result = "W"
            elif pf < pa:
                result = "L"
            else:
                result = "T"

        stats = tgs.stats if isinstance(tgs.stats, dict) else {}

        shots = _to_int(stats.get("shots"))
        hits = _to_int(stats.get("hits"))
        blocked_shots = _to_int(stats.get("blocked_shots"))
        faceoff_pct = _to_float(stats.get("faceoff_pct"))
        giveaways = _to_int(stats.get("giveaways"))
        takeaways = _to_int(stats.get("takeaways"))
        penalty_minutes = _to_int(stats.get("penalty_minutes"))

        power_play_goals = _to_int(stats.get("power_play_goals"))
        power_play_opportunities = _to_int(stats.get("power_play_opportunities"))
        power_play_pct = _to_float(stats.get("power_play_pct"))

        if power_play_pct is None and power_play_goals is not None and power_play_opportunities:
            opps = power_play_opportunities
            if opps and opps > 0:
                power_play_pct = round((power_play_goals / opps) * 100.0, 6)

        shooting_pct = None
        if pf is not None and shots and shots > 0:
            shooting_pct = round((float(pf) / float(shots)) * 100.0, 6)

        shots_vals.append(float(shots) if shots is not None else None)
        hits_vals.append(float(hits) if hits is not None else None)
        blocks_vals.append(float(blocked_shots) if blocked_shots is not None else None)
        faceoff_vals.append(faceoff_pct)
        giveaways_vals.append(float(giveaways) if giveaways is not None else None)
        takeaways_vals.append(float(takeaways) if takeaways is not None else None)
        pp_pct_vals.append(power_play_pct)
        shooting_pct_vals.append(shooting_pct)
        pim_vals.append(float(penalty_minutes) if penalty_minutes is not None else None)

        out_rows.append(
            {
                "idx": idx,
                "date": g.game_date.date().isoformat() if g.game_date else None,
                "opponent": (opp or "").upper(),
                "home_away": "home" if is_home else "away",
                "result": result,
                "pf": pf,
                "pa": pa,
                "margin": margin,
                "shots": shots,
                "hits": hits,
                "blocked_shots": blocked_shots,
                "faceoff_pct": round(faceoff_pct, 6) if faceoff_pct is not None else None,
                "giveaways": giveaways,
                "takeaways": takeaways,
                "penalty_minutes": penalty_minutes,
                "power_play_goals": power_play_goals,
                "power_play_opportunities": power_play_opportunities,
                "power_play_pct": round(power_play_pct, 6) if power_play_pct is not None else None,
                "shooting_pct": round(shooting_pct, 6) if shooting_pct is not None else None,
            }
        )

    for i in range(len(out_rows)):
        out_rows[i][f"shots_roll{roll}"] = (
            round(roll_mean(shots_vals, i), 6) if roll_mean(shots_vals, i) is not None else None
        )
        out_rows[i][f"hits_roll{roll}"] = (
            round(roll_mean(hits_vals, i), 6) if roll_mean(hits_vals, i) is not None else None
        )
        out_rows[i][f"blocks_roll{roll}"] = (
            round(roll_mean(blocks_vals, i), 6) if roll_mean(blocks_vals, i) is not None else None
        )
        out_rows[i][f"faceoff_pct_roll{roll}"] = (
            round(roll_mean(faceoff_vals, i), 6) if roll_mean(faceoff_vals, i) is not None else None
        )
        out_rows[i][f"giveaways_roll{roll}"] = (
            round(roll_mean(giveaways_vals, i), 6) if roll_mean(giveaways_vals, i) is not None else None
        )
        out_rows[i][f"takeaways_roll{roll}"] = (
            round(roll_mean(takeaways_vals, i), 6) if roll_mean(takeaways_vals, i) is not None else None
        )
        out_rows[i][f"pp_pct_roll{roll}"] = (
            round(roll_mean(pp_pct_vals, i), 6) if roll_mean(pp_pct_vals, i) is not None else None
        )
        out_rows[i][f"shooting_pct_roll{roll}"] = (
            round(roll_mean(shooting_pct_vals, i), 6) if roll_mean(shooting_pct_vals, i) is not None else None
        )
        out_rows[i][f"pim_roll{roll}"] = (
            round(roll_mean(pim_vals, i), 6) if roll_mean(pim_vals, i) is not None else None
        )

    return {
        "sport": sport,
        "team": team_code,
        "season": season,
        "season_type": season_type,
        "games": len(out_rows),
        "roll_window": roll,
        "rows": out_rows,
    }