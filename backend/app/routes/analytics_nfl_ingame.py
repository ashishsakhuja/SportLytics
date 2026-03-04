from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

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


def _get_any(d: Dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in d:
            return d.get(k)
    return None


def _parse_ratio(v: Any) -> Tuple[Optional[int], Optional[int]]:
    """Parse '18/27' or '7-13' -> (18,27)."""
    if v is None:
        return (None, None)
    s = str(v).strip()
    if not s:
        return (None, None)
    s = s.replace("/", "-")
    if "-" not in s:
        return (_to_int(s), None)
    left, right = s.split("-", 1)
    return (_to_int(left), _to_int(right))


@router.get("/nfl/teams/{team_code}/in-game/summary")
def nfl_in_game_summary(
    team_code: str,
    season: int = Query(...),
    season_type: str = Query("REG", description="REG/POST"),
    last: int = Query(60, ge=5, le=200, description="Max games to return (oldest->newest)"),
    roll: int = Query(5, ge=2, le=20, description="Rolling window size"),
    db: Session = Depends(get_db),
):
    sport = "nfl"
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

    ypa_vals: List[Optional[float]] = []
    comp_vals: List[Optional[float]] = []
    sack_rate_vals: List[Optional[float]] = []
    pass_rate_vals: List[Optional[float]] = []
    ypp_vals: List[Optional[float]] = []

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
        raw = stats.get("raw_stats") if isinstance(stats.get("raw_stats"), dict) else {}

        # Prefer standardized values
        pass_att = _to_int(stats.get("pass_att"))
        pass_cmp = _to_int(stats.get("pass_cmp"))
        pass_yds = _to_int(stats.get("pass_yds"))
        completion_pct = _to_float(stats.get("completion_pct"))

        rush_att = _to_int(stats.get("rush_att"))
        rush_yds = _to_int(stats.get("rush_yds"))

        total_yds = _to_int(stats.get("total_yds"))
        turnovers = _to_int(stats.get("turnovers"))
        third_down_pct = _to_float(stats.get("third_down_pct"))
        red_zone_td_pct = _to_float(stats.get("red_zone_td_pct"))

        # ---- KEY FIX: fallback from raw C/ATT if pass_att/pass_cmp missing
        if (pass_att is None or pass_cmp is None) and raw:
            ca = _get_any(
                raw,
                "c_att",
                "cmp_att",
                "comp_att",
                "completions_attempts",
                "completion_attempts",
                "passing_completions_attempts",
                "pass_completions_attempts",
            )
            c, a = _parse_ratio(ca)
            if pass_cmp is None:
                pass_cmp = c
            if pass_att is None:
                pass_att = a

        if completion_pct is None and pass_cmp is not None and pass_att is not None and pass_att > 0:
            completion_pct = round((pass_cmp / pass_att) * 100.0, 6)

        # Sacks + yards lost
        sacks = _to_int(stats.get("sacks"))
        sacks_yards_lost = _to_int(stats.get("sacks_yards_lost"))
        if (sacks is None or sacks_yards_lost is None) and raw:
            sacks_raw = _get_any(raw, "sacks_yards_lost", "sacksyardslost", "sacks_yards", "sacks")
            s_cnt, s_yl = _parse_ratio(sacks_raw)
            if sacks is None:
                sacks = s_cnt
            if sacks_yards_lost is None:
                sacks_yards_lost = s_yl

        ypa = (pass_yds / pass_att) if (pass_yds is not None and pass_att) else None
        rypa = (rush_yds / rush_att) if (rush_yds is not None and rush_att) else None

        pass_rate = (
            (pass_att + (sacks or 0)) / ((pass_att + (sacks or 0)) + rush_att)
            if (pass_att is not None and rush_att is not None and ((pass_att + (sacks or 0)) + rush_att) > 0)
            else None
        )

        sack_rate = (
            (sacks / (pass_att + sacks))
            if (sacks is not None and pass_att is not None and (pass_att + sacks) > 0)
            else None
        )

        plays = None
        if pass_att is not None and rush_att is not None:
            plays = pass_att + rush_att + (sacks or 0)

        ypp = (total_yds / plays) if (total_yds is not None and plays and plays > 0) else None

        ypa_vals.append(ypa)
        comp_vals.append(completion_pct)
        sack_rate_vals.append(sack_rate)
        pass_rate_vals.append(pass_rate)
        ypp_vals.append(ypp)

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
                "pass_att": pass_att,
                "pass_cmp": pass_cmp,
                "pass_yds": pass_yds,
                "completion_pct": completion_pct,
                "rush_att": rush_att,
                "rush_yds": rush_yds,
                "total_yds": total_yds,
                "turnovers": turnovers,
                "third_down_pct": third_down_pct,
                "red_zone_td_pct": red_zone_td_pct,
                "sacks": sacks,
                "sacks_yards_lost": sacks_yards_lost,
                "ypa": round(ypa, 6) if ypa is not None else None,
                "rypa": round(rypa, 6) if rypa is not None else None,
                "pass_rate": round(pass_rate, 6) if pass_rate is not None else None,
                "sack_rate": round(sack_rate, 6) if sack_rate is not None else None,
                "plays": plays,
                "ypp": round(ypp, 6) if ypp is not None else None,
            }
        )

    for i in range(len(out_rows)):
        ypa_r = roll_mean(ypa_vals, i)
        comp_r = roll_mean(comp_vals, i)
        sack_r = roll_mean(sack_rate_vals, i)
        pass_r = roll_mean(pass_rate_vals, i)
        ypp_r = roll_mean(ypp_vals, i)

        out_rows[i][f"ypa_roll{roll}"] = round(ypa_r, 6) if ypa_r is not None else None
        out_rows[i][f"comp_roll{roll}"] = round(comp_r, 6) if comp_r is not None else None
        out_rows[i][f"sack_rate_roll{roll}"] = round(sack_r, 6) if sack_r is not None else None
        out_rows[i][f"pass_rate_roll{roll}"] = round(pass_r, 6) if pass_r is not None else None
        out_rows[i][f"ypp_roll{roll}"] = round(ypp_r, 6) if ypp_r is not None else None

    return {
        "sport": sport,
        "team": team_code,
        "season": season,
        "season_type": season_type,
        "games": len(out_rows),
        "roll_window": roll,
        "rows": out_rows,
    }