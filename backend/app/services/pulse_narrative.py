from __future__ import annotations

from typing import Any, Dict, List, Optional

POINTS_LABEL = {"nfl": "points", "nba": "points", "mlb": "runs", "nhl": "goals"}


def _fmt_num(value: Any, digits: int = 1) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _team_label(row: Dict[str, Any]) -> str:
    return row.get("label") or row.get("team_code") or "This team"


def _overall_signal(row: Dict[str, Any]) -> float:
    score = 0.0
    for key in ("margin_delta", "offense_delta", "defense_delta", "turnover_delta"):
        try:
            score += abs(float(row.get(key) or 0.0))
        except Exception:
            pass
    return score


def _metric_value(row: Dict[str, Any], metric_focus: str) -> Optional[float]:
    if metric_focus == "offense":
        return _safe_float(row.get("offense_delta"))
    if metric_focus == "defense":
        return _safe_float(row.get("defense_delta"))
    if metric_focus == "turnovers":
        return _safe_float(row.get("turnover_delta"))
    if metric_focus == "split":
        gap = _safe_float(row.get("home_away_gap"))
        return abs(gap) if gap is not None else None
    if metric_focus == "sos":
        return _safe_float(row.get("recent_sos"))
    if metric_focus == "margin":
        return _safe_float(row.get("margin_delta"))
    return _overall_signal(row)


def storyline_caption(item: Dict[str, Any], sport: str) -> str:
    support = item.get("support") or {}
    category = item.get("category")
    team = item.get("team_label") or item.get("team_code") or "This team"

    if category == "offense":
        return (
            f"{team} is averaging {_fmt_num(support.get('last5_avg_pf'))} {POINTS_LABEL.get(sport, 'points')} "
            f"over its last five, up {_fmt_num(support.get('offense_delta'))} from the previous five."
        )
    if category == "defense":
        return (
            f"{team} has improved its defensive trend by {_fmt_num(support.get('defense_delta'))}, "
            f"with {_fmt_num(support.get('last5_avg_pa'))} allowed over the last five."
        )
    if category == "margin":
        return (
            f"{team} has a recent average margin of {_fmt_num(support.get('last5_avg_margin'))}, "
            f"a shift of {_fmt_num(support.get('margin_delta'))} versus the prior five-game stretch."
        )
    if category == "turnovers":
        return f"{team} has shifted the turnover battle by {_fmt_num(support.get('turnover_delta'))} recently."
    if category == "sos":
        return (
            f"{team}'s recent strength of schedule is {_fmt_num(support.get('recent_sos'))}, "
            f"compared with {_fmt_num(support.get('season_sos'))} for the full season."
        )
    if category == "split":
        return f"{team} shows a home-away margin gap of {_fmt_num(support.get('home_away_gap'))}."
    return f"{team} is showing a notable recent signal."


def _answer_smalltalk(route: Dict[str, Any]) -> str:
    return route.get("message") or "Hello — I’m Pulse, the SportLytics assistant."


def _answer_clarify(route: Dict[str, Any]) -> str:
    return route.get("message") or "Which team are you asking about?"


def _answer_team_compare(items: List[Dict[str, Any]], route: Dict[str, Any], sport: str, metric_focus: str) -> str:
    if not items:
        return "Not enough data yet."

    compare_kind = route.get("compare_kind")
    seasons = route.get("requested_seasons") or []
    stat_word = POINTS_LABEL.get(sport, "points")

    if compare_kind == "teams_and_seasons":
        by_team: Dict[str, List[Dict[str, Any]]] = {}
        for row in items:
            by_team.setdefault(row.get("team_code") or "UNK", []).append(row)
        parts = []
        for team_code, rows in list(by_team.items())[:3]:
            rows = sorted(rows, key=lambda r: r.get("season") or 0)
            first = rows[0]
            last = rows[-1]
            parts.append(
                f"{_team_label(last)} moved from a margin Δ of {_fmt_num(first.get('margin_delta'))} in {first.get('season')} "
                f"to {_fmt_num(last.get('margin_delta'))} in {last.get('season')}"
            )
        return "Across the requested teams and seasons, the clearest takeaway is: " + "; ".join(parts) + "."

    if compare_kind == "seasons":
        rows = sorted(items, key=lambda r: r.get("season") or 0)
        if len(rows) >= 2:
            first = rows[0]
            last = rows[-1]
            return (
                f"{_team_label(last)} changed noticeably from {first.get('season')} to {last.get('season')}. "
                f"Its recent margin delta moved from {_fmt_num(first.get('margin_delta'))} to {_fmt_num(last.get('margin_delta'))}, "
                f"while offense shifted from {_fmt_num(first.get('offense_delta'))} to {_fmt_num(last.get('offense_delta'))} "
                f"and defense from {_fmt_num(first.get('defense_delta'))} to {_fmt_num(last.get('defense_delta'))}."
            )

    if compare_kind == "teams":
        a, b = items[0], items[1] if len(items) > 1 else (items[0], None)
        if b is None:
            return "Not enough data yet."
        season_text = f" in {a.get('season')}" if a.get("season") else ""
        if metric_focus == "offense":
            return (
                f"{_team_label(a)} has the stronger recent offensive signal{season_text}: {_fmt_num(a.get('last5_avg_pf'))} {stat_word} over the last five "
                f"with a delta of {_fmt_num(a.get('offense_delta'))}, versus {_team_label(b)} at {_fmt_num(b.get('last5_avg_pf'))} "
                f"and a delta of {_fmt_num(b.get('offense_delta'))}."
            )
        if metric_focus == "defense":
            return (
                f"{_team_label(a)} has the stronger recent defensive signal{season_text}: {_fmt_num(a.get('last5_avg_pa'))} {stat_word} allowed over the last five "
                f"with a defensive delta of {_fmt_num(a.get('defense_delta'))}, versus {_team_label(b)} at {_fmt_num(b.get('last5_avg_pa'))} "
                f"and a delta of {_fmt_num(b.get('defense_delta'))}."
            )
        return (
            f"{_team_label(a)} has the stronger recent profile{season_text}: margin Δ {_fmt_num(a.get('margin_delta'))}, "
            f"recent record {a.get('recent_record')}, versus {_team_label(b)} at margin Δ {_fmt_num(b.get('margin_delta'))} "
            f"with a recent record of {b.get('recent_record')}."
        )

    return "Not enough data yet."


def _answer_team_trend(items: List[Dict[str, Any]], sport: str) -> str:
    if not items:
        return "Not enough data yet."
    row = items[0]
    stat_word = POINTS_LABEL.get(sport, "points")
    season_text = f" in {row.get('season')}" if row.get("season") else ""
    return (
        f"{_team_label(row)}{season_text} is {row.get('recent_record')} over its last five games with an average margin of "
        f"{_fmt_num(row.get('last5_avg_margin'))}, compared with {_fmt_num(row.get('prev5_avg_margin'))} in the previous five. "
        f"It is averaging {_fmt_num(row.get('last5_avg_pf'))} {stat_word} and allowing {_fmt_num(row.get('last5_avg_pa'))}, "
        f"with offensive and defensive deltas of {_fmt_num(row.get('offense_delta'))} and {_fmt_num(row.get('defense_delta'))}."
    )


def _answer_stat_explain(items: List[Dict[str, Any]], sport: str) -> str:
    if not items:
        return "Not enough data yet."
    row = items[0]
    stat_word = POINTS_LABEL.get(sport, "points")
    offense_delta = _safe_float(row.get("offense_delta")) or 0.0
    defense_delta = _safe_float(row.get("defense_delta")) or 0.0
    reasons: List[str] = []

    if offense_delta < 0:
        reasons.append(
            f"their offense has dipped from {_fmt_num(row.get('prev5_avg_pf'))} to {_fmt_num(row.get('last5_avg_pf'))} {stat_word} per game"
        )
    elif offense_delta > 0:
        reasons.append(
            f"their offense has improved from {_fmt_num(row.get('prev5_avg_pf'))} to {_fmt_num(row.get('last5_avg_pf'))} {stat_word} per game"
        )

    if defense_delta < 0:
        reasons.append(
            f"their defense has slipped from {_fmt_num(row.get('prev5_avg_pa'))} allowed to {_fmt_num(row.get('last5_avg_pa'))} allowed per game"
        )
    elif defense_delta > 0:
        reasons.append(
            f"their defense has tightened from {_fmt_num(row.get('prev5_avg_pa'))} allowed to {_fmt_num(row.get('last5_avg_pa'))} allowed per game"
        )

    reason_text = " and ".join(reasons) if reasons else "their recent profile has been fairly flat"
    return (
        f"{_team_label(row)} has been trending {('down' if (_safe_float(row.get('margin_delta')) or 0) < 0 else 'up')} lately with a "
        f"{row.get('recent_record')} record over the last five games and an average margin of {_fmt_num(row.get('last5_avg_margin'))}. "
        f"The clearest signal is that {reason_text}."
    )


def _answer_league_rank(items: List[Dict[str, Any]], sport: str, metric_focus: str, direction: str, threshold: Optional[float]) -> str:
    if not items:
        return "Not enough data yet."

    stat_word = POINTS_LABEL.get(sport, "points")

    if metric_focus == "offense" and threshold is not None:
        top = items[:4]
        pieces = []
        for row in top:
            last5 = _safe_float(row.get("last5_avg_pf"))
            delta = _safe_float(row.get("offense_delta"))
            if last5 is None:
                continue
            gap = last5 - threshold
            phr = (
                f"{_team_label(row)} at {_fmt_num(last5)} {stat_word} per game over its last five "
                f"({_fmt_num(delta)} delta, {('+' if gap >= 0 else '')}{_fmt_num(gap)} vs {threshold:.0f})"
            )
            pieces.append(phr)
        if pieces:
            return (
                f"The teams most likely to clear {threshold:.0f} {stat_word} in their next game based on recent offensive form are "
                + "; ".join(pieces)
                + "."
            )

    if metric_focus == "offense":
        top = items[:3]
        return (
            "The strongest recent offenses are "
            + "; ".join(
                f"{_team_label(row)} at {_fmt_num(row.get('last5_avg_pf'))} {stat_word} per game over the last five, "
                f"up {_fmt_num(row.get('offense_delta'))} from the previous five"
                for row in top
            )
            + "."
        )

    if metric_focus == "defense":
        top = items[:3]
        return (
            "The strongest recent defensive trends belong to "
            + "; ".join(
                f"{_team_label(row)} allowing {_fmt_num(row.get('last5_avg_pa'))} {stat_word} per game over the last five, "
                f"with a defensive delta of {_fmt_num(row.get('defense_delta'))}"
                for row in top
            )
            + "."
        )

    top = items[:3]
    return (
        "The clearest league-wide recent signals are "
        + "; ".join(
            f"{_team_label(row)} with margin Δ {_fmt_num(row.get('margin_delta'))}, offense Δ {_fmt_num(row.get('offense_delta'))}, "
            f"and defense Δ {_fmt_num(row.get('defense_delta'))}"
            for row in top
        )
        + "."
    )


def _answer_trend_rank(items: List[Dict[str, Any]], sport: str, metric_focus: str, direction: str) -> str:
    if not items:
        return "Not enough data yet."

    top = items[:4]
    direction_text = "up" if direction != "down" else "down"
    stat_word = POINTS_LABEL.get(sport, "points")

    if metric_focus == "offense":
        return (
            f"The teams trending {direction_text} offensively over the last five games are "
            + "; ".join(
                f"{_team_label(row)} at {_fmt_num(row.get('last5_avg_pf'))} {stat_word} per game with an offensive delta of {_fmt_num(row.get('offense_delta'))}"
                for row in top
            )
            + "."
        )

    if metric_focus == "defense":
        return (
            f"The teams trending {direction_text} defensively over the last five games are "
            + "; ".join(
                f"{_team_label(row)} allowing {_fmt_num(row.get('last5_avg_pa'))} {stat_word} with a defensive delta of {_fmt_num(row.get('defense_delta'))}"
                for row in top
            )
            + "."
        )

    return (
        f"The teams trending {direction_text} most clearly right now are "
        + "; ".join(
            f"{_team_label(row)} ({row.get('recent_record')}, margin Δ {_fmt_num(row.get('margin_delta'))})"
            for row in top
        )
        + "."
    )


def answer_for_route(route: Dict[str, Any], context: Dict[str, Any], sport: str) -> str:
    query_type = route.get("query_type")
    items = context.get("items") or []
    metric_focus = route.get("metric_focus", "overall")
    direction = route.get("direction", "neutral")
    threshold = route.get("threshold")

    if query_type == "smalltalk":
        return _answer_smalltalk(route)
    if query_type == "clarify_team":
        return _answer_clarify(route)
    if query_type == "unknown":
        return route.get("message") or "Sorry, I can only analyze sports information."
    if query_type == "team_compare":
        return _answer_team_compare(items, route, sport, metric_focus)
    if query_type == "team_trend":
        return _answer_team_trend(items, sport)
    if query_type == "stat_explain":
        return _answer_stat_explain(items, sport)
    if query_type == "league_rank":
        return _answer_league_rank(items, sport, metric_focus, direction, threshold)
    if query_type == "trend_rank":
        return _answer_trend_rank(items, sport, metric_focus, direction)
    return "Not enough data yet."
