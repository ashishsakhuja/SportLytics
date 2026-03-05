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


@router.get("/nba/teams/{team_code}/in-game/summary")
def nba_in_game_summary(
    team_code: str,
    season: int = Query(...),
    season_type: str = Query("REG", description="REG/POST"),
    last: int = Query(82, ge=5, le=250, description="Max games to return (oldest->newest)"),
    roll: int = Query(5, ge=2, le=20, description="Rolling window size"),
    db: Session = Depends(get_db),
):
    """NBA per-team per-game boxscore analytics (derived from team_game_stats).

    Mirrors the NFL in-game endpoint but with basketball metrics:
      - shooting splits (FG/3PT/FT) + percents
      - possessions estimate
      - eFG%, TS%, points per possession, AST/TOV
      - rolling versions of the above
    """

    sport = "nba"
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

    fg_pct_vals: List[Optional[float]] = []
    tp_pct_vals: List[Optional[float]] = []
    ft_pct_vals: List[Optional[float]] = []
    efg_vals: List[Optional[float]] = []
    ts_vals: List[Optional[float]] = []
    ppp_vals: List[Optional[float]] = []
    ast_tov_vals: List[Optional[float]] = []
    poss_vals: List[Optional[float]] = []

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

        fg_m = _to_int(stats.get("fg_m"))
        fg_a = _to_int(stats.get("fg_a"))
        fg_pct = _to_float(stats.get("fg_pct"))

        tp_m = _to_int(stats.get("tp_m"))
        tp_a = _to_int(stats.get("tp_a"))
        tp_pct = _to_float(stats.get("tp_pct"))

        ft_m = _to_int(stats.get("ft_m"))
        ft_a = _to_int(stats.get("ft_a"))
        ft_pct = _to_float(stats.get("ft_pct"))

        oreb = _to_int(stats.get("oreb"))
        dreb = _to_int(stats.get("dreb"))
        reb = _to_int(stats.get("reb"))
        ast = _to_int(stats.get("ast"))
        tov = _to_int(stats.get("tov"))
        stl = _to_int(stats.get("stl"))
        blk = _to_int(stats.get("blk"))
        pfouls = _to_int(stats.get("pf"))

        possessions_est = _to_float(stats.get("possessions_est"))

        # Derived shooting efficiency
        efg = None
        if fg_m is not None and fg_a and fg_a > 0:
            efg = (fg_m + 0.5 * float(tp_m or 0)) / float(fg_a)

        ts = None
        if pf is not None and fg_a is not None and ft_a is not None:
            denom = 2.0 * (float(fg_a) + 0.44 * float(ft_a))
            if denom > 0:
                ts = float(pf) / denom

        ppp = None
        if pf is not None and possessions_est and possessions_est > 0:
            ppp = float(pf) / float(possessions_est)

        ast_tov = None
        if ast is not None and tov is not None and tov > 0:
            ast_tov = float(ast) / float(tov)

        fg_pct_vals.append(fg_pct)
        tp_pct_vals.append(tp_pct)
        ft_pct_vals.append(ft_pct)
        efg_vals.append(efg)
        ts_vals.append(ts)
        ppp_vals.append(ppp)
        ast_tov_vals.append(ast_tov)
        poss_vals.append(possessions_est)

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
                "fg_m": fg_m,
                "fg_a": fg_a,
                "fg_pct": round(fg_pct, 6) if fg_pct is not None else None,
                "tp_m": tp_m,
                "tp_a": tp_a,
                "tp_pct": round(tp_pct, 6) if tp_pct is not None else None,
                "ft_m": ft_m,
                "ft_a": ft_a,
                "ft_pct": round(ft_pct, 6) if ft_pct is not None else None,
                "oreb": oreb,
                "dreb": dreb,
                "reb": reb,
                "ast": ast,
                "tov": tov,
                "stl": stl,
                "blk": blk,
                "pfouls": pfouls,
                "possessions_est": round(possessions_est, 6) if possessions_est is not None else None,
                "efg": round(efg, 6) if efg is not None else None,
                "ts": round(ts, 6) if ts is not None else None,
                "ppp": round(ppp, 6) if ppp is not None else None,
                "ast_tov": round(ast_tov, 6) if ast_tov is not None else None,
            }
        )

    for i in range(len(out_rows)):
        out_rows[i][f"fg_pct_roll{roll}"] = (
            round(roll_mean(fg_pct_vals, i), 6) if roll_mean(fg_pct_vals, i) is not None else None
        )
        out_rows[i][f"tp_pct_roll{roll}"] = (
            round(roll_mean(tp_pct_vals, i), 6) if roll_mean(tp_pct_vals, i) is not None else None
        )
        out_rows[i][f"ft_pct_roll{roll}"] = (
            round(roll_mean(ft_pct_vals, i), 6) if roll_mean(ft_pct_vals, i) is not None else None
        )
        out_rows[i][f"efg_roll{roll}"] = (
            round(roll_mean(efg_vals, i), 6) if roll_mean(efg_vals, i) is not None else None
        )
        out_rows[i][f"ts_roll{roll}"] = (
            round(roll_mean(ts_vals, i), 6) if roll_mean(ts_vals, i) is not None else None
        )
        out_rows[i][f"ppp_roll{roll}"] = (
            round(roll_mean(ppp_vals, i), 6) if roll_mean(ppp_vals, i) is not None else None
        )
        out_rows[i][f"ast_tov_roll{roll}"] = (
            round(roll_mean(ast_tov_vals, i), 6) if roll_mean(ast_tov_vals, i) is not None else None
        )
        out_rows[i][f"poss_roll{roll}"] = (
            round(roll_mean(poss_vals, i), 6) if roll_mean(poss_vals, i) is not None else None
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
