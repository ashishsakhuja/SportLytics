from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Game, Team, TeamGameStats

router = APIRouter(prefix="/analytics/custom", tags=["analytics-custom"])

SUPPORTED_DATA_SPORTS = {"nfl", "nba", "mlb", "nhl"}

BUILT_IN_METRICS = [
    {"key": "score_for", "label": "Score For", "source": "built_in", "group": "Core"},
    {"key": "score_against", "label": "Score Against", "source": "built_in", "group": "Core"},
    {"key": "margin", "label": "Margin", "source": "built_in", "group": "Core"},
    {"key": "total_score", "label": "Total Score", "source": "built_in", "group": "Core"},
    {"key": "win_flag", "label": "Win Flag", "source": "built_in", "group": "Core"},
    {"key": "loss_flag", "label": "Loss Flag", "source": "built_in", "group": "Core"},
]

METRIC_LABEL_OVERRIDES = {
    "score_for": "Score For",
    "score_against": "Score Against",
    "margin": "Margin",
    "total_score": "Total Score",
    "win_flag": "Win Flag",
    "loss_flag": "Loss Flag",
    "pass_yds": "Pass Yards",
    "rush_yds": "Rush Yards",
    "total_yds": "Total Yards",
    "turnovers": "Turnovers",
    "third_down_pct": "Third Down %",
    "red_zone_td_pct": "Red Zone TD %",
    "sacks": "Sacks",
    "sacks_yards_lost": "Sack Yards Lost",
    "completion_pct": "Completion %",
    "pass_att": "Pass Attempts",
    "pass_cmp": "Pass Completions",
    "rush_att": "Rush Attempts",
    "ypa": "Yards / Pass Attempt",
    "rypa": "Yards / Rush Attempt",
    "pass_rate": "Pass Rate %",
    "rebounds": "Rebounds",
    "assists": "Assists",
    "turnover": "Turnovers",
    "fg_pct": "FG %",
    "three_pt_pct": "3PT %",
    "hits": "Hits",
    "errors": "Errors",
    "shots": "Shots",
    "power_play_pct": "Power Play %",
    "penalty_kill_pct": "Penalty Kill %",
}


def _norm_sport(s: str) -> str:
    s = (s or "").lower().strip()
    if s not in SUPPORTED_DATA_SPORTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported sport '{s}'. Supported: {sorted(SUPPORTED_DATA_SPORTS)}",
        )
    return s


def _norm_season_type(s: str) -> str:
    s = (s or "REG").upper().strip()
    if s not in {"REG", "POST"}:
        raise HTTPException(status_code=400, detail="season_type must be REG or POST")
    return s


def _finalish_filter():
    return sa.and_(
        Game.home_score.isnot(None),
        Game.away_score.isnot(None),
        sa.or_(Game.status == "final", Game.status.is_(None)),
    )


def _get_stat_value(stats: Dict[str, Any], key: str) -> Any:
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
    if "/" in s:
        return None
    if s.endswith("%"):
        s = s[:-1].strip()

    try:
        return float(s)
    except Exception:
        return None


def _metric_label(key: str) -> str:
    if key in METRIC_LABEL_OVERRIDES:
        return METRIC_LABEL_OVERRIDES[key]
    cleaned = key.replace("raw:", "Raw ").replace("_", " ").replace(".", " ")
    return " ".join(part.capitalize() for part in cleaned.split())


def _season_range(start: int, end: int) -> List[int]:
    if end < start:
        raise HTTPException(status_code=400, detail="season_to must be >= season_from")
    if end - start > 12:
        raise HTTPException(status_code=400, detail="Please keep the season range to 12 years or fewer")
    return list(range(start, end + 1))


def _discover_metric_keys(db: Session, sport: str, season: int, season_type: str, limit: int = 2500) -> List[Dict[str, Any]]:
    rows = (
        db.query(TeamGameStats.stats)
        .filter(
            TeamGameStats.sport == sport,
            TeamGameStats.season == season,
            TeamGameStats.season_type == season_type,
        )
        .order_by(TeamGameStats.game_id.desc())
        .limit(limit)
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

    discovered = [
        {
            "key": key,
            "label": _metric_label(key),
            "source": "team_game_stats",
            "group": "Advanced",
            "count": int(count),
        }
        for key, count in c.most_common()
    ]
    return BUILT_IN_METRICS + discovered


def _metric_value(metric: str, team_code: str, game: Game, stats: Optional[Dict[str, Any]]) -> Optional[float]:
    team_code = (team_code or "").upper().strip()
    is_home = (game.home_team_code or "").upper() == team_code

    pf = game.home_score if is_home else game.away_score
    pa = game.away_score if is_home else game.home_score

    if metric == "score_for":
        return float(pf) if pf is not None else None
    if metric == "score_against":
        return float(pa) if pa is not None else None
    if metric == "margin":
        return float(pf - pa) if pf is not None and pa is not None else None
    if metric == "total_score":
        return float(pf + pa) if pf is not None and pa is not None else None
    if metric == "win_flag":
        return 1.0 if pf is not None and pa is not None and pf > pa else 0.0
    if metric == "loss_flag":
        return 1.0 if pf is not None and pa is not None and pf < pa else 0.0

    val = _get_stat_value(stats or {}, metric)
    return _coerce_number(val)


def _apply_filters(row: Dict[str, Any], home_away: str, result: str) -> bool:
    if home_away != "all" and row.get("home_away") != home_away:
        return False
    if result != "all" and row.get("result") != result:
        return False
    return True


def _roll(values: List[Optional[float]], window: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        slice_vals = [v for v in values[start : i + 1] if v is not None]
        out.append(round(sum(slice_vals) / len(slice_vals), 6) if slice_vals else None)
    return out


def _rows_for_team(
    db: Session,
    *,
    sport: str,
    team_code: str,
    season_from: int,
    season_to: int,
    season_type: str,
    metric: str,
    home_away: str,
    result: str,
) -> List[Dict[str, Any]]:
    seasons = _season_range(season_from, season_to)

    rows = (
        db.query(Game, TeamGameStats)
        .outerjoin(
            TeamGameStats,
            sa.and_(
                TeamGameStats.game_id == Game.id,
                TeamGameStats.team_code == team_code,
                TeamGameStats.sport == sport,
            ),
        )
        .filter(
            Game.sport == sport,
            Game.season.in_(seasons),
            Game.season_type == season_type,
            _finalish_filter(),
            sa.or_(Game.home_team_code == team_code, Game.away_team_code == team_code),
        )
        .order_by(Game.season.asc(), Game.game_date.asc().nullslast(), Game.id.asc())
        .all()
    )

    out: List[Dict[str, Any]] = []
    for idx, (g, tgs) in enumerate(rows, start=1):
        is_home = (g.home_team_code or "").upper() == team_code
        opp = (g.away_team_code if is_home else g.home_team_code) or ""
        pf = g.home_score if is_home else g.away_score
        pa = g.away_score if is_home else g.home_score

        result_label: Optional[str] = None
        if pf is not None and pa is not None:
            if pf > pa:
                result_label = "W"
            elif pf < pa:
                result_label = "L"
            else:
                result_label = "T"

        value = _metric_value(metric, team_code, g, tgs.stats if tgs else None)
        row = {
            "idx": idx,
            "season": g.season,
            "date": g.game_date.date().isoformat() if g.game_date else None,
            "game_id": g.id,
            "team": team_code,
            "opponent": (opp or "").upper(),
            "home_away": "home" if is_home else "away",
            "result": result_label,
            "value": value,
            "score_for": pf,
            "score_against": pa,
            "x": f"{g.season}-{idx}",
        }
        if _apply_filters(row, home_away, result):
            out.append(row)

    return out


def _rows_for_league_average(
    db: Session,
    *,
    sport: str,
    season_from: int,
    season_to: int,
    season_type: str,
    metric: str,
) -> Dict[int, float]:
    seasons = _season_range(season_from, season_to)
    rows = (
        db.query(Game, TeamGameStats)
        .join(TeamGameStats, TeamGameStats.game_id == Game.id)
        .filter(
            Game.sport == sport,
            Game.season.in_(seasons),
            Game.season_type == season_type,
            TeamGameStats.sport == sport,
            _finalish_filter(),
        )
        .order_by(Game.game_date.asc().nullslast(), Game.id.asc())
        .all()
    )

    season_vals: Dict[int, List[float]] = defaultdict(list)
    for g, tgs in rows:
        if g.season is None:
            continue
        team_code = (tgs.team_code or "").upper()
        value = _metric_value(metric, team_code, g, tgs.stats if tgs else None)
        if value is not None:
            season_vals[int(g.season)].append(float(value))

    return {
        season: round(sum(vals) / len(vals), 6)
        for season, vals in season_vals.items()
        if vals
    }


def _season_aggregate(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        season = row.get("season")
        if season is not None:
            grouped[int(season)].append(row)

    out: List[Dict[str, Any]] = []
    for season in sorted(grouped.keys()):
        vals = [r["value"] for r in grouped[season] if r.get("value") is not None]
        out.append(
            {
                "season": season,
                "x": str(season),
                "value": round(sum(vals) / len(vals), 6) if vals else None,
                "games": len(grouped[season]),
            }
        )
    return out


@router.get("/options")
def custom_builder_options(
    sport: str = Query(..., description="nfl/nba/mlb/nhl"),
    season: int = Query(...),
    season_type: str = Query("REG", description="REG/POST"),
    db: Session = Depends(get_db),
):
    sport = _norm_sport(sport)
    season_type = _norm_season_type(season_type)

    teams = (
        db.query(Team)
        .filter(Team.sport == sport)
        .order_by(Team.team_code.asc())
        .all()
    )
    metrics = _discover_metric_keys(db, sport, season, season_type)

    return {
        "sport": sport,
        "season": season,
        "season_type": season_type,
        "teams": [
            {
                "team_code": t.team_code,
                "name": t.name,
                "city": t.city,
                "label": f"{t.city} {t.name}".strip() if t.city else t.name,
            }
            for t in teams
        ],
        "metrics": metrics,
        "compare_modes": [
            {"key": "none", "label": "No Comparison"},
            {"key": "team", "label": "Another Team"},
            {"key": "league_avg", "label": "League Average"},
            {"key": "previous_season", "label": "Previous Season"},
        ],
        "granularities": [
            {"key": "game", "label": "Game by Game"},
            {"key": "season", "label": "Season Average"},
        ],
        "chart_types": [
            {"key": "line", "label": "Line"},
            {"key": "bar", "label": "Bar"},
            {"key": "area", "label": "Area"},
            {"key": "scatter", "label": "Scatter"},
        ],
    }


@router.get("/plot")
def custom_builder_plot(
    sport: str = Query(..., description="nfl/nba/mlb/nhl"),
    team: str = Query(..., description="Primary team code"),
    season_from: int = Query(..., ge=2000),
    season_to: int = Query(..., ge=2000),
    season_type: str = Query("REG", description="REG/POST"),
    metric: str = Query(..., description="Metric key"),
    compare_mode: str = Query("none", description="none/team/league_avg/previous_season"),
    compare_team: Optional[str] = Query(None, description="Comparison team code when compare_mode=team"),
    granularity: str = Query("game", description="game/season"),
    home_away: str = Query("all", description="all/home/away"),
    result: str = Query("all", description="all/W/L/T"),
    roll_window: int = Query(1, ge=1, le=20),
    db: Session = Depends(get_db),
):
    sport = _norm_sport(sport)
    team = (team or "").upper().strip()
    season_type = _norm_season_type(season_type)
    compare_mode = (compare_mode or "none").strip().lower()
    granularity = (granularity or "game").strip().lower()
    home_away = (home_away or "all").strip().lower()
    result = (result or "all").strip().upper()

    if compare_mode not in {"none", "team", "league_avg", "previous_season"}:
        raise HTTPException(status_code=400, detail="Unsupported compare_mode")
    if granularity not in {"game", "season"}:
        raise HTTPException(status_code=400, detail="granularity must be game or season")
    if home_away not in {"all", "home", "away"}:
        raise HTTPException(status_code=400, detail="home_away must be all/home/away")
    if result not in {"ALL", "W", "L", "T"}:
        raise HTTPException(status_code=400, detail="result must be all/W/L/T")

    base_rows = _rows_for_team(
        db,
        sport=sport,
        team_code=team,
        season_from=season_from,
        season_to=season_to,
        season_type=season_type,
        metric=metric,
        home_away=home_away,
        result="all" if result == "ALL" else result,
    )
    if not base_rows:
        raise HTTPException(status_code=404, detail="No data found for the selected filters")

    compare_label = None
    compare_rows: List[Dict[str, Any]] = []
    compare_season_map: Dict[int, float] = {}

    if compare_mode == "team":
        compare_team = (compare_team or "").upper().strip()
        if not compare_team:
            raise HTTPException(status_code=400, detail="compare_team is required when compare_mode=team")
        compare_rows = _rows_for_team(
            db,
            sport=sport,
            team_code=compare_team,
            season_from=season_from,
            season_to=season_to,
            season_type=season_type,
            metric=metric,
            home_away=home_away,
            result="all" if result == "ALL" else result,
        )
        compare_label = compare_team
    elif compare_mode == "league_avg":
        compare_season_map = _rows_for_league_average(
            db,
            sport=sport,
            season_from=season_from,
            season_to=season_to,
            season_type=season_type,
            metric=metric,
        )
        compare_label = "League Avg"
    elif compare_mode == "previous_season":
        prev_rows = _rows_for_team(
            db,
            sport=sport,
            team_code=team,
            season_from=season_from - 1,
            season_to=season_to - 1,
            season_type=season_type,
            metric=metric,
            home_away=home_away,
            result="all" if result == "ALL" else result,
        )
        compare_rows = prev_rows
        compare_label = "Previous Season"

    if granularity == "season":
        primary = _season_aggregate(base_rows)
        compare = _season_aggregate(compare_rows) if compare_rows else []
        compare_map = {str(r["season"]): r.get("value") for r in compare}
        rows: List[Dict[str, Any]] = []
        for row in primary:
            x = row["x"]
            compare_val = None
            if compare_mode == "league_avg":
                compare_val = compare_season_map.get(int(row["season"]))
            else:
                compare_val = compare_map.get(x)
            rows.append({**row, "compare_value": compare_val})
    else:
        values = [r.get("value") for r in base_rows]
        roll_vals = _roll(values, roll_window)

        compare_roll_vals: List[Optional[float]] = []
        if compare_rows:
            compare_roll_vals = _roll([r.get("value") for r in compare_rows], roll_window)

        rows = []
        for i, row in enumerate(base_rows):
            compare_val = None
            if compare_mode == "team":
                compare_val = compare_rows[i].get("value") if i < len(compare_rows) else None
            elif compare_mode == "previous_season":
                compare_val = compare_rows[i].get("value") if i < len(compare_rows) else None
            elif compare_mode == "league_avg":
                season = int(row["season"])
                compare_val = compare_season_map.get(season)

            out_row = {
                **row,
                "x": row.get("date") or f"G{row.get('idx')}",
                "roll_value": roll_vals[i],
                "compare_value": compare_val,
                "compare_roll_value": compare_roll_vals[i] if i < len(compare_roll_vals) else None,
            }
            rows.append(out_row)

    valid_primary = [r.get("value") for r in rows if r.get("value") is not None]
    valid_compare = [r.get("compare_value") for r in rows if r.get("compare_value") is not None]

    return {
        "sport": sport,
        "team": team,
        "season_from": season_from,
        "season_to": season_to,
        "season_type": season_type,
        "metric": metric,
        "metric_label": _metric_label(metric),
        "compare_mode": compare_mode,
        "compare_label": compare_label,
        "granularity": granularity,
        "roll_window": roll_window,
        "filters": {
            "home_away": home_away,
            "result": result,
        },
        "summary": {
            "points": len(rows),
            "primary_avg": round(sum(valid_primary) / len(valid_primary), 6) if valid_primary else None,
            "primary_min": round(min(valid_primary), 6) if valid_primary else None,
            "primary_max": round(max(valid_primary), 6) if valid_primary else None,
            "compare_avg": round(sum(valid_compare) / len(valid_compare), 6) if valid_compare else None,
        },
        "rows": rows,
    }
