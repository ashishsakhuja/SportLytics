from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.services.team_aliases import TEAM_ALIASES

QUERY_TYPES = {"team_trend", "team_compare", "league_rank", "trend_rank", "stat_explain"}

OFFENSE_TERMS = {"offense", "offensive", "score", "scoring", "points", "runs", "goals", "attack"}
DEFENSE_TERMS = {"defense", "defensive", "allowed", "allowing", "preventing", "stopping"}
TURNOVER_TERMS = {"turnover", "turnovers", "takeaways", "giveaways"}
SOS_TERMS = {"sos", "schedule", "strength of schedule", "tough schedule", "hard schedule"}
SPLIT_TERMS = {"home", "away", "road", "split", "location"}
MARGIN_TERMS = {"margin", "differential", "point differential", "run differential", "goal differential"}
TREND_TERMS = {"trend", "trending", "improving", "improved", "improvement", "rising", "up", "surging", "heating up", "declining", "falling", "sliding", "recent", "lately", "last 5", "previous 5"}
RANK_TERMS = {"best", "worst", "top", "bottom", "rank", "ranking", "leader", "leaders"}
COMPARE_TERMS = {"compare", "versus", "vs", "against", "better"}
EXPLAIN_TERMS = {"why", "explain", "how come", "what happened", "what is causing", "reason"}
UP_TERMS = {"up", "improving", "improved", "rising", "surging", "heating up", "better"}
DOWN_TERMS = {"down", "declining", "falling", "sliding", "worse", "struggling"}


def extract_team_codes(question: str, known_codes: set[str]) -> List[str]:
    q = f" {(question or '').lower()} "
    found: List[str] = []

    alias_items = sorted(TEAM_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True)
    for alias, code in alias_items:
        if code not in known_codes or code in found:
            continue
        pattern = rf"(?<![a-z]){re.escape(alias.lower())}(?![a-z])"
        if re.search(pattern, q):
            found.append(code)

    for code in sorted(known_codes):
        if code in found:
            continue
        pattern = rf"(?<![a-z]){re.escape(code.lower())}(?![a-z])"
        if re.search(pattern, q):
            found.append(code)

    return found[:4]


def _contains_any(text: str, phrases: set[str]) -> bool:
    return any(p in text for p in phrases)


def _infer_metric_focus(text: str) -> str:
    if _contains_any(text, TURNOVER_TERMS):
        return "turnovers"
    if _contains_any(text, SOS_TERMS):
        return "sos"
    if _contains_any(text, SPLIT_TERMS):
        return "split"
    if _contains_any(text, DEFENSE_TERMS):
        return "defense"
    if _contains_any(text, OFFENSE_TERMS):
        return "offense"
    if _contains_any(text, MARGIN_TERMS):
        return "margin"
    return "overall"


def _infer_direction(text: str) -> str:
    if _contains_any(text, DOWN_TERMS):
        return "down"
    if _contains_any(text, UP_TERMS):
        return "up"
    return "neutral"


def route_query(
    *,
    question: str,
    known_codes: set[str],
    team_filter: Optional[str] = None,
) -> Dict[str, Any]:
    raw_question = (question or "").strip()
    text = raw_question.lower()
    team_filter = (team_filter or "").upper().strip() or None

    teams = extract_team_codes(raw_question, known_codes)
    if team_filter and team_filter in known_codes and team_filter not in teams:
        teams = [team_filter, *teams][:4]

    metric_focus = _infer_metric_focus(text)
    direction = _infer_direction(text)
    has_compare = _contains_any(text, COMPARE_TERMS)
    has_rank = _contains_any(text, RANK_TERMS)
    has_trend = _contains_any(text, TREND_TERMS)
    has_explain = _contains_any(text, EXPLAIN_TERMS)

    if has_compare or len(teams) >= 2:
        query_type = "team_compare"
    elif has_explain:
        query_type = "stat_explain"
    elif has_rank and has_trend:
        query_type = "trend_rank"
    elif has_rank:
        query_type = "league_rank"
    elif teams or team_filter:
        query_type = "team_trend"
    elif has_trend:
        query_type = "trend_rank"
    else:
        query_type = "league_rank"

    rank_order = "desc"
    if query_type in {"league_rank", "trend_rank"}:
        if metric_focus == "defense":
            rank_order = "desc" if direction == "up" else "asc"
        elif metric_focus == "turnovers":
            rank_order = "desc" if direction == "up" else "asc"
        elif metric_focus == "split":
            rank_order = "desc"
        elif metric_focus == "sos":
            rank_order = "desc" if direction in {"up", "neutral"} else "asc"
        else:
            rank_order = "desc" if direction in {"up", "neutral"} else "asc"

    return {
        "query_type": query_type,
        "teams": teams,
        "metric_focus": metric_focus,
        "direction": direction,
        "window": "last5_vs_prev5",
        "scope": "team" if teams or team_filter else "league",
        "rank_order": rank_order,
        "raw_question": raw_question,
    }
