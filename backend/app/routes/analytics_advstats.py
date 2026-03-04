from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Game, TeamGameStats

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
    """ESPN providers typically use: pre / in / final."""
    return sa.and_(
        Game.home_score.isnot(None),
        Game.away_score.isnot(None),
        sa.or_(Game.status == "final", Game.status.is_(None)),
    )


def _get_stat_value(stats: Dict[str, Any], key: str) -> Any:
    """
    Supports:
      - top-level keys: "pass_yds"
      - raw keys: "raw:total_yards" -> stats["raw_stats"]["total_yards"]
      - nested: "meta.provider" via dot path (rare)
    """
    if not stats or not key:
        return None

    if key.startswith("raw:"):
        raw_key = key.split("raw:", 1)[1]
        raw = stats.get("raw_stats") or {}
        return raw.get(raw_key)

    cur: Any = stats
    for part in key.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _coerce_number(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)

    s = str(v).strip()
    if not s:
        return None

    # Many ESPN stats are "made/att" strings (e.g. 12/18). Skip to avoid misleading charts.
    if "/" in s:
        return None

    # "53.2%" -> 53.2
    if s.endswith("%"):
        s = s[:-1].strip()

    try:
        return float(s)
    except Exception:
        return None


@router.get("/league/{sport}/advanced-stats/keys")
def advanced_stat_keys(
    sport: str,
    season: int = Query(...),
    season_type: str = Query("REG", description="REG/POST"),
    sample: int = Query(2000, ge=200, le=15000, description="Rows to sample for key discovery"),
    db: Session = Depends(get_db),
):
    """
    Return discovered stat keys for the selected league slice.

    - Returns BOTH standardized keys (top-level) and raw keys (prefixed with 'raw:')
    - Keys are discovered by sampling TeamGameStats rows (fast + avoids heavy JSON introspection queries)
    """
    sport = _norm_sport(sport)
    season_type = (season_type or "").upper().strip()
    if season_type not in {"REG", "POST"}:
        raise HTTPException(status_code=400, detail="season_type must be REG or POST")

    rows = (
        db.query(TeamGameStats.stats)
        .filter(
            TeamGameStats.sport == sport,
            TeamGameStats.season == season,
            TeamGameStats.season_type == season_type,
        )
        .order_by(TeamGameStats.game_id.desc())
        .limit(sample)
        .all()
    )

    c: Counter[str] = Counter()
    for (stats,) in rows:
        if not isinstance(stats, dict):
            continue

        for k in stats.keys():
            if k in {"raw_stats", "meta"}:
                continue
            c[k] += 1

        raw = stats.get("raw_stats")
        if isinstance(raw, dict):
            for rk in raw.keys():
                c[f"raw:{rk}"] += 1

    keys = [{"key": k, "count": int(v)} for k, v in c.most_common()]

    return {
        "sport": sport,
        "season": season,
        "season_type": season_type,
        "sampled_rows": len(rows),
        "keys": keys,
    }


@router.get("/teams/{sport}/{team_code}/advanced-stats/timeseries")
def team_advanced_stat_timeseries(
    sport: str,
    team_code: str,
    season: int = Query(...),
    season_type: str = Query("REG", description="REG/POST"),
    key: str = Query(..., description="Stat key (e.g. pass_yds, turnovers, raw:total_yards)"),
    last: int = Query(50, ge=5, le=200, description="Max games to return (oldest->newest)"),
    roll: int = Query(5, ge=2, le=20, description="Rolling window size"),
    db: Session = Depends(get_db),
):
    """
    Per-game timeseries for a single advanced stat key.
    Includes value, rolling average, and cumulative average.
    """
    sport = _norm_sport(sport)
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
        raise HTTPException(status_code=404, detail="No advanced stats found for team/season.")

    rows = list(reversed(rows))  # oldest -> newest

    series: List[Dict[str, Any]] = []
    values: List[Optional[float]] = []

    for idx, (g, tgs) in enumerate(rows, start=1):
        is_home = (g.home_team_code or "").upper() == team_code
        opp = (g.away_team_code if is_home else g.home_team_code) or ""

        pf = g.home_score if is_home else g.away_score
        pa = g.away_score if is_home else g.home_score

        result: Optional[str] = None
        if pf is not None and pa is not None:
            if pf > pa:
                result = "W"
            elif pf < pa:
                result = "L"
            else:
                result = "T"

        stats = tgs.stats if isinstance(tgs.stats, dict) else {}
        raw_v = _get_stat_value(stats, key)
        v = _coerce_number(raw_v)

        values.append(v)
        series.append(
            {
                "idx": idx,
                "date": g.game_date.date().isoformat() if g.game_date else None,
                "opponent": (opp or "").upper(),
                "home_away": "home" if is_home else "away",
                "result": result,
                "value": v,
            }
        )

    cum_sum = 0.0
    cum_n = 0

    for i in range(len(series)):
        v = series[i]["value"]
        if v is not None:
            cum_sum += float(v)
            cum_n += 1
        series[i]["cum_avg"] = round(cum_sum / cum_n, 6) if cum_n else None

        window_vals: List[float] = []
        for j in range(max(0, i - roll + 1), i + 1):
            vv = series[j]["value"]
            if vv is not None:
                window_vals.append(float(vv))
        series[i][f"roll{roll}"] = round(sum(window_vals) / len(window_vals), 6) if window_vals else None

    valid = [v for v in values if v is not None]
    return {
        "sport": sport,
        "team": team_code,
        "season": season,
        "season_type": season_type,
        "key": key,
        "games": len(series),
        "roll_window": roll,
        "avg": (round(sum(valid) / len(valid), 6) if valid else None),
        "rows": series,
    }