from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Any, Dict, Iterable, List, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Game, Team, TeamGameStats

router = APIRouter(prefix="/analytics/custom", tags=["analytics-custom"])

SUPPORTED_DATA_SPORTS = {"nfl", "nba", "mlb", "nhl"}
MAX_OVERLAY_TEAMS = 5

_ALLOWED_TEAM_CODES = {
    "nfl": {
        "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
        "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
        "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
        "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS", "WSH",
    },
    "nba": {
        "ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GS", "HOU", "IND",
        "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NO", "NY", "OKC", "ORL", "PHI", "PHX",
        "POR", "SAC", "SA", "TOR", "UTA", "WSH",
    },
    "mlb": {
        "ARI", "ATL", "BAL", "BOS", "CHC", "CHW", "CIN", "CLE", "COL", "DET", "HOU", "KC",
        "LAA", "LAD", "MIA", "MIL", "MIN", "NYM", "NYY", "ATH", "PHI", "PIT", "SD", "SEA",
        "SF", "STL", "TB", "TEX", "TOR", "WSH",
    },
    "nhl": {
        "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL", "DAL", "DET", "EDM", "FLA",
        "LA", "MIN", "MTL", "NJD", "NSH", "NYI", "NYR", "OTT", "PHI", "PIT", "SEA", "SJ",
        "STL", "TB", "TOR", "UTA", "VAN", "VGK", "WPG", "WSH",
    },
}


def _allowed_team_codes_for_sport(sport: str) -> set[str]:
    return set(_ALLOWED_TEAM_CODES.get((sport or "").lower().strip(), set()))

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


# ---------- helpers ----------


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
    if not s or "/" in s:
        return None
    if s.endswith("%"):
        s = s[:-1].strip()
    try:
        return float(s)
    except Exception:
        return None



def _metric_label(key: Optional[str]) -> str:
    if not key:
        return "Metric"
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



def _safe_series_key(prefix: str, value: str) -> str:
    s = f"{prefix}_{value}".lower().strip()
    return "".join(ch if ch.isalnum() else "_" for ch in s)



def _parse_team_list(primary_team: str, overlay_teams: Optional[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in [primary_team, *(((overlay_teams or "").split(",")) if overlay_teams else [])]:
        t = (raw or "").upper().strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out[:MAX_OVERLAY_TEAMS]



def _date_label(game_date: Optional[date], season: Optional[int], idx: int) -> str:
    if game_date:
        if season is not None:
            return f"{season}-{game_date.isoformat()}"
        return game_date.isoformat()
    if season is not None:
        return f"{season}-G{idx}"
    return f"G{idx}"



def _rows_for_team_metric(
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
            "x": _date_label(g.game_date.date() if g.game_date else None, g.season, idx),
            "point_label": g.game_date.date().isoformat() if g.game_date else f"G{idx}",
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



def _build_overlay_rows(series_rows: Dict[str, List[Dict[str, Any]]], roll_window: int) -> List[Dict[str, Any]]:
    key_meta: Dict[str, Dict[str, Any]] = {}

    def _sort_key(row: Dict[str, Any], fallback_index: int) -> tuple:
        season = int(row.get("season") or 0)
        date_value = row.get("date") or ""
        idx = int(row.get("idx") or (fallback_index + 1))
        x = str(row.get("x") or f"P{fallback_index + 1}")
        return (season, date_value, idx, x)

    for series_key, rows in series_rows.items():
        rolled = _roll([r.get("value") for r in rows], roll_window)
        for i, row in enumerate(rows):
            x = row.get("x") or f"P{i + 1}"
            row_sort_key = _sort_key(row, i)
            meta = key_meta.setdefault(
                x,
                {
                    "x": x,
                    "label": row.get("point_label") or x,
                    "tooltipLabel": row.get("date") or row.get("point_label") or x,
                    "season": row.get("season"),
                    "date": row.get("date"),
                    "opponent": row.get("opponent"),
                    "home_away": row.get("home_away"),
                    "result": row.get("result"),
                    "_sort_key": row_sort_key,
                },
            )
            if row_sort_key < meta.get("_sort_key", row_sort_key):
                meta["_sort_key"] = row_sort_key
                meta["label"] = row.get("point_label") or x
                meta["tooltipLabel"] = row.get("date") or row.get("point_label") or x
                meta["season"] = row.get("season")
                meta["date"] = row.get("date")
                meta["opponent"] = row.get("opponent")
                meta["home_away"] = row.get("home_away")
                meta["result"] = row.get("result")
            meta[series_key] = row.get("value")
            meta[f"{series_key}__roll"] = rolled[i]

    ordered_rows = sorted(key_meta.values(), key=lambda row: row.get("_sort_key", (0, "", 0, str(row.get("x") or ""))))
    for row in ordered_rows:
        row.pop("_sort_key", None)
    return ordered_rows



def _summarize_series(rows: List[Dict[str, Any]], key: str) -> Dict[str, Optional[float]]:
    vals = [r.get(key) for r in rows if isinstance(r.get(key), (int, float))]
    if not vals:
        return {"avg": None, "min": None, "max": None}
    nums = [float(v) for v in vals]
    return {
        "avg": round(sum(nums) / len(nums), 6),
        "min": round(min(nums), 6),
        "max": round(max(nums), 6),
    }



def _build_scatter_points(
    *,
    team_rows: Dict[str, List[Dict[str, Any]]],
    metric_x: str,
    metric_y: str,
    db: Session,
    sport: str,
    season_from: int,
    season_to: int,
    season_type: str,
    home_away: str,
    result: str,
) -> Dict[str, Any]:
    scatter_series = []
    all_x: List[float] = []
    all_y: List[float] = []
    for team_code, rows_x in team_rows.items():
        rows_y = _rows_for_team_metric(
            db,
            sport=sport,
            team_code=team_code,
            season_from=season_from,
            season_to=season_to,
            season_type=season_type,
            metric=metric_y,
            home_away=home_away,
            result=result,
        )
        points = []
        for i, row_x in enumerate(rows_x):
            row_y = rows_y[i] if i < len(rows_y) else None
            x_val = row_x.get("value")
            y_val = row_y.get("value") if row_y else None
            if x_val is None or y_val is None:
                continue
            points.append(
                {
                    "x": x_val,
                    "y": y_val,
                    "label": row_x.get("point_label") or row_x.get("date") or f"Point {i + 1}",
                    "tooltipLabel": f"{team_code} • {row_x.get('date') or row_x.get('point_label') or f'Point {i + 1}'}",
                    "opponent": row_x.get("opponent"),
                    "home_away": row_x.get("home_away"),
                    "result": row_x.get("result"),
                }
            )
            all_x.append(float(x_val))
            all_y.append(float(y_val))
        scatter_series.append(
            {
                "key": _safe_series_key("team", team_code),
                "label": team_code,
                "kind": "team",
                "team": team_code,
                "points": points,
            }
        )

    x_summary = {"avg": round(sum(all_x) / len(all_x), 6), "min": round(min(all_x), 6), "max": round(max(all_x), 6)} if all_x else {"avg": None, "min": None, "max": None}
    y_summary = {"avg": round(sum(all_y) / len(all_y), 6), "min": round(min(all_y), 6), "max": round(max(all_y), 6)} if all_y else {"avg": None, "min": None, "max": None}
    return {"series": scatter_series, "x_summary": x_summary, "y_summary": y_summary}


# ---------- routes ----------


@router.get("/options")
def custom_builder_options(
    sport: str = Query(..., description="nfl/nba/mlb/nhl"),
    season: int = Query(...),
    season_type: str = Query("REG", description="REG/POST"),
    db: Session = Depends(get_db),
):
    sport = _norm_sport(sport)
    season_type = _norm_season_type(season_type)

    teams = db.query(Team).filter(Team.sport == sport).order_by(Team.team_code.asc()).all()
    allowed = _allowed_team_codes_for_sport(sport)
    if allowed:
        teams = [t for t in teams if (t.team_code or "").upper().strip() in allowed] or teams
    metrics = _discover_metric_keys(db, sport, season, season_type)

    return {
        "sport": sport,
        "season": season,
        "season_type": season_type,
        "max_overlay_teams": MAX_OVERLAY_TEAMS,
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
            {"key": "overlay", "label": "Multiple Team Overlay"},
            {"key": "metric", "label": "Metric vs Metric"},
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
        "presets": [
            {"key": "team_form", "label": "Team Form"},
            {"key": "metric_vs_metric", "label": "Metric vs Metric"},
            {"key": "team_overlay", "label": "Team Overlay"},
            {"key": "team_vs_league", "label": "Team vs League Avg"},
            {"key": "scatter_profile", "label": "Scatter Profile"},
        ],
    }


@router.get("/plot")
def custom_builder_plot(
    sport: str = Query(..., description="nfl/nba/mlb/nhl"),
    team: str = Query(..., description="Primary team code"),
    season_from: int = Query(..., ge=2000),
    season_to: int = Query(..., ge=2000),
    season_type: str = Query("REG", description="REG/POST"),
    metric: str = Query(..., description="Primary metric key"),
    secondary_metric: Optional[str] = Query(None, description="Second metric key for metric compare or scatter"),
    compare_mode: str = Query("none", description="none/overlay/metric/league_avg/previous_season"),
    overlay_teams: Optional[str] = Query(None, description="Comma-separated team codes"),
    granularity: str = Query("game", description="game/season"),
    home_away: str = Query("all", description="all/home/away"),
    result: str = Query("all", description="all/W/L/T"),
    roll_window: int = Query(1, ge=1, le=20),
    chart_type: str = Query("line", description="line/bar/area/scatter"),
    db: Session = Depends(get_db),
):
    sport = _norm_sport(sport)
    team = (team or "").upper().strip()
    season_type = _norm_season_type(season_type)
    compare_mode = (compare_mode or "none").strip().lower()
    granularity = (granularity or "game").strip().lower()
    home_away = (home_away or "all").strip().lower()
    result_norm = (result or "all").strip().upper()
    chart_type = (chart_type or "line").strip().lower()
    compare_result = "all" if result_norm == "ALL" else result_norm

    if compare_mode not in {"none", "overlay", "metric", "league_avg", "previous_season"}:
        raise HTTPException(status_code=400, detail="Unsupported compare_mode")
    if granularity not in {"game", "season"}:
        raise HTTPException(status_code=400, detail="granularity must be game or season")
    if home_away not in {"all", "home", "away"}:
        raise HTTPException(status_code=400, detail="home_away must be all/home/away")
    if result_norm not in {"ALL", "W", "L", "T"}:
        raise HTTPException(status_code=400, detail="result must be all/W/L/T")
    if chart_type not in {"line", "bar", "area", "scatter"}:
        raise HTTPException(status_code=400, detail="Unsupported chart_type")
    if chart_type == "scatter" and not secondary_metric:
        raise HTTPException(status_code=400, detail="secondary_metric is required for scatter mode")
    if compare_mode == "metric" and not secondary_metric:
        raise HTTPException(status_code=400, detail="secondary_metric is required when compare_mode=metric")

    teams = _parse_team_list(team, overlay_teams)
    if not teams:
        raise HTTPException(status_code=400, detail="A primary team is required")

    team_rows_metric_1: Dict[str, List[Dict[str, Any]]] = {}
    for team_code in teams:
        rows = _rows_for_team_metric(
            db,
            sport=sport,
            team_code=team_code,
            season_from=season_from,
            season_to=season_to,
            season_type=season_type,
            metric=metric,
            home_away=home_away,
            result=compare_result,
        )
        if rows:
            team_rows_metric_1[team_code] = rows

    if team not in team_rows_metric_1:
        raise HTTPException(status_code=404, detail="No data found for the selected filters")

    if chart_type == "scatter":
        scatter = _build_scatter_points(
            team_rows=team_rows_metric_1,
            metric_x=metric,
            metric_y=secondary_metric or "",
            db=db,
            sport=sport,
            season_from=season_from,
            season_to=season_to,
            season_type=season_type,
            home_away=home_away,
            result=compare_result,
        )
        return {
            "sport": sport,
            "team": team,
            "teams": list(team_rows_metric_1.keys()),
            "season_from": season_from,
            "season_to": season_to,
            "season_type": season_type,
            "chart_type": chart_type,
            "metric": metric,
            "metric_label": _metric_label(metric),
            "secondary_metric": secondary_metric,
            "secondary_metric_label": _metric_label(secondary_metric),
            "compare_mode": "metric" if secondary_metric else compare_mode,
            "compare_label": _metric_label(secondary_metric) if secondary_metric else None,
            "granularity": granularity,
            "roll_window": roll_window,
            "filters": {"home_away": home_away, "result": result_norm},
            "series": scatter["series"],
            "rows": [],
            "summary": {
                "points": sum(len(s.get("points", [])) for s in scatter["series"]),
                "primary_avg": scatter["x_summary"]["avg"],
                "primary_min": scatter["x_summary"]["min"],
                "primary_max": scatter["x_summary"]["max"],
                "compare_avg": scatter["y_summary"]["avg"],
                "compare_min": scatter["y_summary"]["min"],
                "compare_max": scatter["y_summary"]["max"],
            },
        }

    rows: List[Dict[str, Any]] = []
    series_meta: List[Dict[str, Any]] = []

    if compare_mode == "overlay":
        overlay_rows_source: Dict[str, List[Dict[str, Any]]] = {}
        for team_code, team_rows in team_rows_metric_1.items():
            src_rows = _season_aggregate(team_rows) if granularity == "season" else team_rows
            key = _safe_series_key("team", team_code)
            overlay_rows_source[key] = src_rows
            series_meta.append(
                {
                    "key": key,
                    "label": team_code,
                    "kind": "team",
                    "team": team_code,
                    "metric": metric,
                    "metric_label": _metric_label(metric),
                    "roll_key": f"{key}__roll",
                }
            )
        rows = _build_overlay_rows(overlay_rows_source, roll_window)

    elif compare_mode == "metric":
        primary_rows = _season_aggregate(team_rows_metric_1[team]) if granularity == "season" else team_rows_metric_1[team]
        secondary_rows = _rows_for_team_metric(
            db,
            sport=sport,
            team_code=team,
            season_from=season_from,
            season_to=season_to,
            season_type=season_type,
            metric=secondary_metric or "",
            home_away=home_away,
            result=compare_result,
        )
        secondary_rows = _season_aggregate(secondary_rows) if granularity == "season" else secondary_rows
        primary_key = _safe_series_key("metric", metric)
        secondary_key = _safe_series_key("metric", secondary_metric or "secondary")
        rows = []
        for i, row in enumerate(primary_rows):
            other = secondary_rows[i] if i < len(secondary_rows) else None
            rows.append(
                {
                    "x": row.get("x"),
                    "label": row.get("point_label") or row.get("x"),
                    "tooltipLabel": row.get("date") or row.get("point_label") or row.get("x"),
                    "season": row.get("season"),
                    "date": row.get("date"),
                    "opponent": row.get("opponent"),
                    "home_away": row.get("home_away"),
                    "result": row.get("result"),
                    primary_key: row.get("value"),
                    secondary_key: other.get("value") if other else None,
                }
            )
        rolled_primary = _roll([r.get(primary_key) for r in rows], roll_window)
        rolled_secondary = _roll([r.get(secondary_key) for r in rows], roll_window)
        for i, row in enumerate(rows):
            row[f"{primary_key}__roll"] = rolled_primary[i]
            row[f"{secondary_key}__roll"] = rolled_secondary[i]
        series_meta = [
            {
                "key": primary_key,
                "label": _metric_label(metric),
                "kind": "metric",
                "team": team,
                "metric": metric,
                "metric_label": _metric_label(metric),
                "roll_key": f"{primary_key}__roll",
            },
            {
                "key": secondary_key,
                "label": _metric_label(secondary_metric),
                "kind": "metric",
                "team": team,
                "metric": secondary_metric,
                "metric_label": _metric_label(secondary_metric),
                "roll_key": f"{secondary_key}__roll",
            },
        ]

    elif compare_mode == "league_avg":
        primary_rows = _season_aggregate(team_rows_metric_1[team]) if granularity == "season" else team_rows_metric_1[team]
        compare_season_map = _rows_for_league_average(
            db,
            sport=sport,
            season_from=season_from,
            season_to=season_to,
            season_type=season_type,
            metric=metric,
        )
        primary_key = _safe_series_key("team", team)
        compare_key = _safe_series_key("compare", "league_avg")
        rows = []
        for row in primary_rows:
            season_value = compare_season_map.get(int(row.get("season"))) if row.get("season") is not None else None
            rows.append(
                {
                    "x": row.get("x"),
                    "label": row.get("point_label") or row.get("x"),
                    "tooltipLabel": row.get("date") or row.get("point_label") or row.get("x"),
                    "season": row.get("season"),
                    "date": row.get("date"),
                    "opponent": row.get("opponent"),
                    "home_away": row.get("home_away"),
                    "result": row.get("result"),
                    primary_key: row.get("value"),
                    compare_key: season_value,
                }
            )
        rolled_primary = _roll([r.get(primary_key) for r in rows], roll_window)
        for i, row in enumerate(rows):
            row[f"{primary_key}__roll"] = rolled_primary[i]
        series_meta = [
            {
                "key": primary_key,
                "label": team,
                "kind": "team",
                "team": team,
                "metric": metric,
                "metric_label": _metric_label(metric),
                "roll_key": f"{primary_key}__roll",
            },
            {
                "key": compare_key,
                "label": "League Avg",
                "kind": "compare",
                "team": None,
                "metric": metric,
                "metric_label": _metric_label(metric),
                "roll_key": None,
            },
        ]

    elif compare_mode == "previous_season":
        primary_rows = _season_aggregate(team_rows_metric_1[team]) if granularity == "season" else team_rows_metric_1[team]
        previous_rows = _rows_for_team_metric(
            db,
            sport=sport,
            team_code=team,
            season_from=season_from - 1,
            season_to=season_to - 1,
            season_type=season_type,
            metric=metric,
            home_away=home_away,
            result=compare_result,
        )
        previous_rows = _season_aggregate(previous_rows) if granularity == "season" else previous_rows
        primary_key = _safe_series_key("team", team)
        compare_key = _safe_series_key("compare", "previous_season")
        rows = []
        for i, row in enumerate(primary_rows):
            other = previous_rows[i] if i < len(previous_rows) else None
            rows.append(
                {
                    "x": row.get("x"),
                    "label": row.get("point_label") or row.get("x"),
                    "tooltipLabel": row.get("date") or row.get("point_label") or row.get("x"),
                    "season": row.get("season"),
                    "date": row.get("date"),
                    "opponent": row.get("opponent"),
                    "home_away": row.get("home_away"),
                    "result": row.get("result"),
                    primary_key: row.get("value"),
                    compare_key: other.get("value") if other else None,
                }
            )
        rolled_primary = _roll([r.get(primary_key) for r in rows], roll_window)
        rolled_compare = _roll([r.get(compare_key) for r in rows], roll_window)
        for i, row in enumerate(rows):
            row[f"{primary_key}__roll"] = rolled_primary[i]
            row[f"{compare_key}__roll"] = rolled_compare[i]
        series_meta = [
            {
                "key": primary_key,
                "label": team,
                "kind": "team",
                "team": team,
                "metric": metric,
                "metric_label": _metric_label(metric),
                "roll_key": f"{primary_key}__roll",
            },
            {
                "key": compare_key,
                "label": "Previous Season",
                "kind": "compare",
                "team": team,
                "metric": metric,
                "metric_label": _metric_label(metric),
                "roll_key": f"{compare_key}__roll",
            },
        ]

    else:
        primary_rows = _season_aggregate(team_rows_metric_1[team]) if granularity == "season" else team_rows_metric_1[team]
        primary_key = _safe_series_key("team", team)
        rows = []
        for row in primary_rows:
            rows.append(
                {
                    "x": row.get("x"),
                    "label": row.get("point_label") or row.get("x"),
                    "tooltipLabel": row.get("date") or row.get("point_label") or row.get("x"),
                    "season": row.get("season"),
                    "date": row.get("date"),
                    "opponent": row.get("opponent"),
                    "home_away": row.get("home_away"),
                    "result": row.get("result"),
                    primary_key: row.get("value"),
                }
            )
        rolled_primary = _roll([r.get(primary_key) for r in rows], roll_window)
        for i, row in enumerate(rows):
            row[f"{primary_key}__roll"] = rolled_primary[i]
        series_meta = [
            {
                "key": primary_key,
                "label": team,
                "kind": "team",
                "team": team,
                "metric": metric,
                "metric_label": _metric_label(metric),
                "roll_key": f"{primary_key}__roll",
            }
        ]

    if not rows:
        raise HTTPException(status_code=404, detail="No data found for the selected filters")

    summary_primary = _summarize_series(rows, series_meta[0]["key"]) if series_meta else {"avg": None, "min": None, "max": None}
    summary_compare = _summarize_series(rows, series_meta[1]["key"]) if len(series_meta) > 1 else {"avg": None, "min": None, "max": None}

    return {
        "sport": sport,
        "team": team,
        "teams": teams,
        "season_from": season_from,
        "season_to": season_to,
        "season_type": season_type,
        "chart_type": chart_type,
        "metric": metric,
        "metric_label": _metric_label(metric),
        "secondary_metric": secondary_metric,
        "secondary_metric_label": _metric_label(secondary_metric),
        "compare_mode": compare_mode,
        "compare_label": series_meta[1]["label"] if len(series_meta) > 1 else None,
        "granularity": granularity,
        "roll_window": roll_window,
        "filters": {"home_away": home_away, "result": result_norm},
        "series": series_meta,
        "summary": {
            "points": len(rows),
            "primary_avg": summary_primary["avg"],
            "primary_min": summary_primary["min"],
            "primary_max": summary_primary["max"],
            "compare_avg": summary_compare["avg"],
            "compare_min": summary_compare["min"],
            "compare_max": summary_compare["max"],
        },
        "rows": rows,
    }
