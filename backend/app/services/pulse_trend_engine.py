from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import Game, Team, TeamGameStats

SUPPORTED_SPORTS = {"nfl", "nba", "mlb", "nhl"}


def normalize_sport(sport: str) -> str:
    sport = (sport or "").lower().strip()
    if sport not in SUPPORTED_SPORTS:
        raise ValueError(f"Unsupported sport '{sport}'")
    return sport


def normalize_season_type(season_type: str | None) -> str:
    return (season_type or "REG").upper().strip()


def _finalish_filter():
    return sa.and_(
        Game.home_score.isnot(None),
        Game.away_score.isnot(None),
        sa.or_(Game.status == "final", Game.status.is_(None)),
    )


def _safe_avg(values: List[Optional[float]]) -> Optional[float]:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _round(v: Optional[float], digits: int = 2) -> Optional[float]:
    if v is None:
        return None
    return round(float(v), digits)


def _wins_losses_ties(rows: List[Dict[str, Any]]) -> tuple[int, int, int]:
    wins = sum(1 for r in rows if r["result"] == "W")
    losses = sum(1 for r in rows if r["result"] == "L")
    ties = sum(1 for r in rows if r["result"] == "T")
    return wins, losses, ties


def _record_string(rows: List[Dict[str, Any]]) -> str:
    wins, losses, ties = _wins_losses_ties(rows)
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def _team_label_map(db: Session, sport: str) -> Dict[str, str]:
    rows = db.query(Team).filter(Team.sport == sport).all()
    out: Dict[str, str] = {}
    for row in rows:
        label = f"{row.city} {row.name}".strip() if row.city else row.name
        out[row.team_code.upper()] = label
    return out


def _load_team_game_rows(
    db: Session,
    *,
    sport: str,
    season: int,
    season_type: str,
    team_code: str | None = None,
) -> List[Dict[str, Any]]:
    q = (
        db.query(Game)
        .filter(
            Game.sport == sport,
            Game.season == season,
            Game.season_type == season_type,
            Game.game_date.isnot(None),
            _finalish_filter(),
        )
        .order_by(Game.game_date.asc(), Game.id.asc())
    )

    rows: List[Dict[str, Any]] = []
    for g in q.all():
        for side in ("home", "away"):
            is_home = side == "home"
            code = (g.home_team_code if is_home else g.away_team_code).upper()
            if team_code and code != team_code:
                continue
            pf = g.home_score if is_home else g.away_score
            pa = g.away_score if is_home else g.home_score
            if pf is None or pa is None:
                continue
            rows.append(
                {
                    "game_id": g.id,
                    "team_code": code,
                    "date": g.game_date,
                    "home_away": "home" if is_home else "away",
                    "opponent": (g.away_team_code if is_home else g.home_team_code).upper(),
                    "pf": int(pf),
                    "pa": int(pa),
                    "margin": int(pf) - int(pa),
                    "result": "W" if pf > pa else ("L" if pf < pa else "T"),
                }
            )
    return rows


def _load_turnovers_by_team(
    db: Session,
    *,
    sport: str,
    season: int,
    season_type: str,
) -> Dict[tuple[int, str], Optional[float]]:
    rows = (
        db.query(TeamGameStats.game_id, TeamGameStats.team_code, TeamGameStats.stats)
        .filter(
            TeamGameStats.sport == sport,
            TeamGameStats.season == season,
            TeamGameStats.season_type == season_type,
        )
        .all()
    )

    out: Dict[tuple[int, str], Optional[float]] = {}
    for game_id, code, stats in rows:
        stats = stats or {}
        value = stats.get("turnovers")
        try:
            out[(int(game_id), str(code).upper())] = None if value is None else float(value)
        except Exception:
            out[(int(game_id), str(code).upper())] = None
    return out


def _compute_win_pct_by_team(rows_by_team: Dict[str, List[Dict[str, Any]]]) -> Dict[str, float]:
    win_pct: Dict[str, float] = {}
    for code, rows in rows_by_team.items():
        if not rows:
            win_pct[code] = 0.0
            continue
        wins = sum(1 for r in rows if r["result"] == "W")
        ties = sum(1 for r in rows if r["result"] == "T")
        win_pct[code] = (wins + 0.5 * ties) / len(rows)
    return win_pct


def _avg_opponent_win_pct(rows: List[Dict[str, Any]], win_pct_by_team: Dict[str, float]) -> Optional[float]:
    values = [win_pct_by_team.get(r["opponent"]) for r in rows if r.get("opponent") in win_pct_by_team]
    return _safe_avg(values)


def _metric_delta(last_val: Optional[float], prev_val: Optional[float]) -> Optional[float]:
    if last_val is None or prev_val is None:
        return None
    return last_val - prev_val


def compute_league_trend_summaries(
    db: Session,
    *,
    sport: str,
    season: int,
    season_type: str,
    team_code: str | None = None,
) -> List[Dict[str, Any]]:
    sport = normalize_sport(sport)
    season_type = normalize_season_type(season_type)
    team_code = (team_code or "").upper().strip() or None

    label_map = _team_label_map(db, sport)
    game_rows = _load_team_game_rows(db, sport=sport, season=season, season_type=season_type, team_code=team_code)
    turnover_lookup = _load_turnovers_by_team(db, sport=sport, season=season, season_type=season_type)

    rows_by_team: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in game_rows:
        row["turnovers"] = turnover_lookup.get((row["game_id"], row["team_code"]))
        rows_by_team[row["team_code"]].append(row)

    win_pct_by_team = _compute_win_pct_by_team(rows_by_team)

    summaries: List[Dict[str, Any]] = []
    for code, rows in rows_by_team.items():
        rows = sorted(rows, key=lambda x: (x["date"], x["game_id"]))
        last5 = rows[-5:]
        prev5 = rows[-10:-5]
        home_rows = [r for r in rows if r["home_away"] == "home"]
        away_rows = [r for r in rows if r["home_away"] == "away"]
        wins, losses, ties = _wins_losses_ties(rows)
        recent_wins, recent_losses, recent_ties = _wins_losses_ties(last5)

        season_avg_pf = _safe_avg([r["pf"] for r in rows])
        season_avg_pa = _safe_avg([r["pa"] for r in rows])
        season_avg_margin = _safe_avg([r["margin"] for r in rows])

        last5_pf = _safe_avg([r["pf"] for r in last5])
        last5_pa = _safe_avg([r["pa"] for r in last5])
        last5_margin = _safe_avg([r["margin"] for r in last5])
        last5_turnovers = _safe_avg([r.get("turnovers") for r in last5])

        prev5_pf = _safe_avg([r["pf"] for r in prev5])
        prev5_pa = _safe_avg([r["pa"] for r in prev5])
        prev5_margin = _safe_avg([r["margin"] for r in prev5])
        prev5_turnovers = _safe_avg([r.get("turnovers") for r in prev5])

        home_avg_margin = _safe_avg([r["margin"] for r in home_rows])
        away_avg_margin = _safe_avg([r["margin"] for r in away_rows])
        season_sos = _avg_opponent_win_pct(rows, win_pct_by_team)
        recent_sos = _avg_opponent_win_pct(last5, win_pct_by_team)

        summary = {
            "team_code": code,
            "label": label_map.get(code, code),
            "games": len(rows),
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "season_avg_pf": _round(season_avg_pf),
            "season_avg_pa": _round(season_avg_pa),
            "season_avg_margin": _round(season_avg_margin),
            "last5_avg_pf": _round(last5_pf),
            "last5_avg_pa": _round(last5_pa),
            "last5_avg_margin": _round(last5_margin),
            "prev5_avg_pf": _round(prev5_pf),
            "prev5_avg_pa": _round(prev5_pa),
            "prev5_avg_margin": _round(prev5_margin),
            "offense_delta": _round(_metric_delta(last5_pf, prev5_pf)),
            "defense_delta": _round(_metric_delta(prev5_pa, last5_pa)),
            "margin_delta": _round(_metric_delta(last5_margin, prev5_margin)),
            "last5_avg_turnovers": _round(last5_turnovers),
            "prev5_avg_turnovers": _round(prev5_turnovers),
            "turnover_delta": _round(_metric_delta(prev5_turnovers, last5_turnovers)),
            "home_avg_margin": _round(home_avg_margin),
            "away_avg_margin": _round(away_avg_margin),
            "home_away_gap": _round(_metric_delta(home_avg_margin, away_avg_margin)),
            "recent_record": f"{recent_wins}-{recent_losses}" + (f"-{recent_ties}" if recent_ties else ""),
            "recent_win_pct": _round((recent_wins + 0.5 * recent_ties) / len(last5) if last5 else None),
            "season_sos": _round(season_sos, 3),
            "recent_sos": _round(recent_sos, 3),
            "sos_delta": _round(_metric_delta(recent_sos, season_sos), 3),
            "latest_game_date": rows[-1]["date"].isoformat() if rows else None,
        }
        summaries.append(summary)

    summaries.sort(
        key=lambda s: (
            s.get("margin_delta") if s.get("margin_delta") is not None else -9999,
            s.get("season_avg_margin") if s.get("season_avg_margin") is not None else -9999,
        ),
        reverse=True,
    )
    return summaries


def compute_team_trend_summary(
    db: Session,
    *,
    sport: str,
    season: int,
    season_type: str,
    team_code: str,
) -> Optional[Dict[str, Any]]:
    team_code = (team_code or "").upper().strip()
    if not team_code:
        return None
    summaries = compute_league_trend_summaries(
        db,
        sport=sport,
        season=season,
        season_type=season_type,
        team_code=team_code,
    )
    return summaries[0] if summaries else None
