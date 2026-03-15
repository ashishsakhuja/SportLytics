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


@router.get("/mlb/teams/{team_code}/in-game/summary")
def mlb_in_game_summary(
    team_code: str,
    season: int = Query(...),
    season_type: str = Query("REG", description="REG/POST"),
    last: int = Query(162, ge=5, le=220, description="Max games to return (oldest->newest)"),
    roll: int = Query(5, ge=2, le=20, description="Rolling window size"),
    db: Session = Depends(get_db),
):
    sport = "mlb"
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

    runs_vals: List[Optional[float]] = []
    hits_vals: List[Optional[float]] = []
    hr_vals: List[Optional[float]] = []
    bb_vals: List[Optional[float]] = []
    so_vals: List[Optional[float]] = []
    obp_vals: List[Optional[float]] = []
    slg_vals: List[Optional[float]] = []
    ops_vals: List[Optional[float]] = []
    iso_vals: List[Optional[float]] = []
    kbb_vals: List[Optional[float]] = []
    sb_vals: List[Optional[float]] = []

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

        stats = tgs.stats if isinstance(tgs.stats, dict) else {}

        ab = _to_int(stats.get("ab"))
        hits = _to_int(stats.get("hits"))
        doubles = _to_int(stats.get("doubles"))
        triples = _to_int(stats.get("triples"))
        home_runs = _to_int(stats.get("home_runs"))
        rbi = _to_int(stats.get("rbi"))
        walks = _to_int(stats.get("walks"))
        strikeouts = _to_int(stats.get("strikeouts"))
        stolen_bases = _to_int(stats.get("stolen_bases"))
        left_on_base = _to_int(stats.get("left_on_base"))
        total_bases = _to_int(stats.get("total_bases"))

        batting_avg = _to_float(stats.get("batting_avg"))
        obp = _to_float(stats.get("obp"))
        slg = _to_float(stats.get("slg"))
        ops = _to_float(stats.get("ops"))

        # Derived fallbacks
        if total_bases is None and hits is not None:
            d = doubles or 0
            t = triples or 0
            hr = home_runs or 0
            singles = hits - d - t - hr
            total_bases = singles + 2 * d + 3 * t + 4 * hr

        if batting_avg is None and hits is not None and ab and ab > 0:
            batting_avg = round(hits / ab, 6)

        if obp is None and hits is not None and walks is not None and ab is not None:
            denom = ab + walks
            if denom > 0:
                obp = round((hits + walks) / denom, 6)

        if slg is None and total_bases is not None and ab and ab > 0:
            slg = round(total_bases / ab, 6)

        if ops is None and obp is not None and slg is not None:
            ops = round(obp + slg, 6)

        iso = None
        if slg is not None and batting_avg is not None:
            iso = round(slg - batting_avg, 6)

        kbb = None
        if strikeouts is not None and walks is not None:
            if walks > 0:
                kbb = round(strikeouts / walks, 6)

        runs_vals.append(float(pf) if pf is not None else None)
        hits_vals.append(float(hits) if hits is not None else None)
        hr_vals.append(float(home_runs) if home_runs is not None else None)
        bb_vals.append(float(walks) if walks is not None else None)
        so_vals.append(float(strikeouts) if strikeouts is not None else None)
        obp_vals.append(obp)
        slg_vals.append(slg)
        ops_vals.append(ops)
        iso_vals.append(iso)
        kbb_vals.append(kbb)
        sb_vals.append(float(stolen_bases) if stolen_bases is not None else None)

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
                "ab": ab,
                "hits": hits,
                "doubles": doubles,
                "triples": triples,
                "home_runs": home_runs,
                "rbi": rbi,
                "walks": walks,
                "strikeouts": strikeouts,
                "stolen_bases": stolen_bases,
                "left_on_base": left_on_base,
                "total_bases": total_bases,
                "batting_avg": round(batting_avg, 6) if batting_avg is not None else None,
                "obp": round(obp, 6) if obp is not None else None,
                "slg": round(slg, 6) if slg is not None else None,
                "ops": round(ops, 6) if ops is not None else None,
                "iso": round(iso, 6) if iso is not None else None,
                "kbb": round(kbb, 6) if kbb is not None else None,
            }
        )

    for i in range(len(out_rows)):
        out_rows[i][f"runs_roll{roll}"] = (
            round(roll_mean(runs_vals, i), 6) if roll_mean(runs_vals, i) is not None else None
        )
        out_rows[i][f"hits_roll{roll}"] = (
            round(roll_mean(hits_vals, i), 6) if roll_mean(hits_vals, i) is not None else None
        )
        out_rows[i][f"hr_roll{roll}"] = (
            round(roll_mean(hr_vals, i), 6) if roll_mean(hr_vals, i) is not None else None
        )
        out_rows[i][f"bb_roll{roll}"] = (
            round(roll_mean(bb_vals, i), 6) if roll_mean(bb_vals, i) is not None else None
        )
        out_rows[i][f"so_roll{roll}"] = (
            round(roll_mean(so_vals, i), 6) if roll_mean(so_vals, i) is not None else None
        )
        out_rows[i][f"obp_roll{roll}"] = (
            round(roll_mean(obp_vals, i), 6) if roll_mean(obp_vals, i) is not None else None
        )
        out_rows[i][f"slg_roll{roll}"] = (
            round(roll_mean(slg_vals, i), 6) if roll_mean(slg_vals, i) is not None else None
        )
        out_rows[i][f"ops_roll{roll}"] = (
            round(roll_mean(ops_vals, i), 6) if roll_mean(ops_vals, i) is not None else None
        )
        out_rows[i][f"iso_roll{roll}"] = (
            round(roll_mean(iso_vals, i), 6) if roll_mean(iso_vals, i) is not None else None
        )
        out_rows[i][f"kbb_roll{roll}"] = (
            round(roll_mean(kbb_vals, i), 6) if roll_mean(kbb_vals, i) is not None else None
        )
        out_rows[i][f"sb_roll{roll}"] = (
            round(roll_mean(sb_vals, i), 6) if roll_mean(sb_vals, i) is not None else None
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
