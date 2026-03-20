from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.team_aliases import TEAM_ALIASES

QUERY_TYPES = {
    "team_trend",
    "team_compare",
    "league_rank",
    "trend_rank",
    "stat_explain",
    "predictive",
    "news_summary",
    "news_impact",
    "smalltalk",
    "unknown",
    "clarify_team",
}

GREETING_TERMS = {
    "hello",
    "hi",
    "hey",
    "hey pulse",
    "hello pulse",
    "good morning",
    "good afternoon",
    "good evening",
}

SMALLTALK_TERMS = {
    "how are you",
    "who are you",
    "what can you do",
    "thanks",
    "thank you",
    "help",
}

OFFENSE_TERMS = {
    "offense",
    "offensive",
    "score",
    "scores",
    "scoring",
    "scored",
    "points",
    "runs",
    "goals",
    "attack",
    "put up",
}

DEFENSE_TERMS = {
    "defense",
    "defensive",
    "allowed",
    "allowing",
    "preventing",
    "stopping",
    "points allowed",
    "runs allowed",
    "goals allowed",
}

TURNOVER_TERMS = {"turnover", "turnovers", "takeaways", "giveaways"}
SOS_TERMS = {"sos", "schedule", "strength of schedule"}
SPLIT_TERMS = {"home", "away", "road", "split"}
MARGIN_TERMS = {"margin", "differential"}

TREND_TERMS = {
    "trend",
    "trending",
    "improving",
    "rising",
    "recent",
    "lately",
    "last 5",
    "last five",
    "hot",
    "cold",
    "heating up",
}

RANK_TERMS = {
    "best",
    "worst",
    "top",
    "bottom",
    "rank",
    "ranking",
    "ranked",
    "leaders",
    "leader",
    "highest",
    "lowest",
    "most",
    "least",
}

COMPARE_TERMS = {"compare", "versus", "vs", "against"}
EXPLAIN_TERMS = {"why", "explain", "how come", "reason", "struggling"}
UP_TERMS = {"up", "improving", "rising", "surging", "better", "hotter"}
DOWN_TERMS = {"down", "declining", "falling", "sliding", "struggling", "worse", "cold"}
PREDICTIVE_TERMS = {
    "predict",
    "prediction",
    "project",
    "projected",
    "forecast",
    "future",
    "going forward",
    "rest of the season",
    "next game",
    "next few",
    "likely",
    "likelihood",
    "expected",
    "expect",
    "should they",
    "will they",
    "how do we think",
    "what do we think",
}
NEWS_TERMS = {
    "news", "headline", "headlines", "report", "reports", "rumor", "rumors", "update", "updates",
    "injury", "injuries", "availability", "status", "inactive", "out", "questionable", "doubtful",
    "trade", "trades", "traded", "transaction", "transactions", "waived", "released", "signed",
    "lineup", "starter", "starters", "suspended", "suspension", "return", "returns", "returning", "activated"
}
IMPACT_TERMS = {
    "impact", "affect", "affects", "affecting", "matter", "matters", "difference", "changes", "changed",
    "because of", "based on the news", "because of injuries", "because of trades", "injury impact",
    "trade impact", "availability impact", "roster impact", "lineup impact"
}

SPORTS_INTENT_TERMS = {
    "team",
    "teams",
    "game",
    "games",
    "offense",
    "defense",
    "score",
    "scores",
    "scoring",
    "points",
    "rank",
    "ranking",
    "trend",
    "trending",
    "matchup",
    "season",
    "record",
    "nfl",
    "nba",
    "mlb",
    "nhl",
    "touchdown",
    "td",
    "yards",
    "allowed",
    "win",
    "wins",
    "losses",
}

THRESHOLD_PATTERN = re.compile(r"\b(over|under|more than|less than|at least|at most)\s+(\d+(?:\.\d+)?)\b")
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
LAST_N_SEASONS_PATTERN = re.compile(r"\b(?:last|past|previous)\s+(\d+)\s+(?:seasons|years)\b")
CURRENT_YEAR = datetime.now().year


def extract_team_codes(question: str, known_codes: set[str]) -> List[str]:
    q = f" {(question or '').lower()} "
    found: List[str] = []

    alias_items = sorted(TEAM_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True)

    for alias, code in alias_items:
        if known_codes and code not in known_codes:
            continue
        if code in found:
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

    return found[:6]


def extract_requested_seasons(question: str, default_season: int | None = None) -> List[int]:
    text = (question or "").lower().strip()
    seasons: List[int] = []

    explicit_years = [int(m.group(1)) for m in YEAR_PATTERN.finditer(text)]
    for year in explicit_years:
        if year not in seasons:
            seasons.append(year)

    if seasons:
        return seasons[:4]

    match = LAST_N_SEASONS_PATTERN.search(text)
    if match:
        try:
            count = max(1, min(4, int(match.group(1))))
        except Exception:
            count = 2
        start = int(default_season or CURRENT_YEAR)
        return [start - idx for idx in range(count)]

    if any(p in text for p in {"last season", "previous season"}):
        start = int(default_season or CURRENT_YEAR) - 1
        return [start]

    if "this season" in text or "current season" in text:
        return [int(default_season or CURRENT_YEAR)]

    return [int(default_season)] if default_season is not None else []


def extract_requested_season_type(question: str, default_season_type: str | None = None) -> str | None:
    text = (question or "").lower().strip()
    if any(p in text for p in {"playoff", "playoffs", "postseason", "post season"}):
        return "POST"
    if any(p in text for p in {"regular season", "reg season"}):
        return "REG"
    return default_season_type or None


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


def _has_sports_intent(text: str, teams: List[str]) -> bool:
    if teams:
        return True
    if _contains_any(text, SPORTS_INTENT_TERMS):
        return True
    if THRESHOLD_PATTERN.search(text):
        return True
    return False


def route_query(
    *,
    question: str,
    known_codes: set[str],
    team_filter: Optional[str] = None,
    default_season: int | None = None,
    default_season_type: str | None = None,
) -> Dict[str, Any]:
    raw_question = (question or "").strip()
    text = raw_question.lower()

    teams = extract_team_codes(raw_question, known_codes)
    filter_code = (team_filter or "").upper().strip()
    if filter_code and filter_code in known_codes and not teams:
        teams = [filter_code]
    has_sports_intent = _has_sports_intent(text, teams)

    requested_seasons = extract_requested_seasons(raw_question, default_season)
    requested_season = requested_seasons[0] if requested_seasons else default_season
    requested_season_type = extract_requested_season_type(raw_question, default_season_type)

    if (_contains_any(text, GREETING_TERMS) or _contains_any(text, SMALLTALK_TERMS)) and not has_sports_intent:
        return {
            "query_type": "smalltalk",
            "raw_question": raw_question,
            "requested_season": requested_season,
            "requested_season_type": requested_season_type,
            "requested_seasons": requested_seasons,
        }

    metric_focus = _infer_metric_focus(text)
    direction = _infer_direction(text)

    has_compare = _contains_any(text, COMPARE_TERMS)
    has_rank = _contains_any(text, RANK_TERMS)
    has_trend = _contains_any(text, TREND_TERMS)
    has_explain = _contains_any(text, EXPLAIN_TERMS)
    has_threshold = THRESHOLD_PATTERN.search(text) is not None
    has_multi_team = len(teams) >= 2
    has_multi_season = len(requested_seasons) >= 2
    wants_prediction = _contains_any(text, PREDICTIVE_TERMS)
    wants_news = _contains_any(text, NEWS_TERMS)
    wants_impact = _contains_any(text, IMPACT_TERMS)

    if wants_prediction and has_sports_intent:
        # Predictive questions that mention news or injuries should still route to
        # the predictive pipeline, which can then pull in recent headlines as context.
        query_type = "predictive"
    elif wants_news and wants_impact and has_sports_intent:
        query_type = "news_impact"
    elif wants_news and has_sports_intent:
        query_type = "news_summary"
    elif has_compare or has_multi_team or has_multi_season:
        query_type = "team_compare"
    elif has_explain and teams:
        query_type = "stat_explain"
    elif has_explain and not teams and has_sports_intent:
        return {
            "query_type": "clarify_team",
            "message": "Which team are you asking about?",
            "raw_question": raw_question,
            "requested_season": requested_season,
            "requested_season_type": requested_season_type,
            "requested_seasons": requested_seasons,
        }
    elif has_rank and has_trend:
        query_type = "trend_rank"
    elif has_rank:
        query_type = "league_rank"
    elif teams:
        query_type = "team_trend"
    elif has_trend:
        query_type = "trend_rank"
    elif has_threshold and metric_focus == "offense":
        query_type = "league_rank"
    elif has_sports_intent:
        query_type = "league_rank"
    else:
        return {
            "query_type": "unknown",
            "message": "Sorry, I can only analyze sports information. Try asking about team trends, offense, defense, rankings, predictions, or news impact.",
            "raw_question": raw_question,
            "requested_season": requested_season,
            "requested_season_type": requested_season_type,
            "requested_seasons": requested_seasons,
        }

    threshold = None
    threshold_match = THRESHOLD_PATTERN.search(text)
    if threshold_match:
        try:
            threshold = float(threshold_match.group(2))
        except Exception:
            threshold = None

    compare_kind = None
    if query_type == "team_compare":
        if has_multi_team and has_multi_season:
            compare_kind = "teams_and_seasons"
        elif has_multi_team:
            compare_kind = "teams"
        elif has_multi_season:
            compare_kind = "seasons"
        else:
            compare_kind = "teams"

    return {
        "query_type": query_type,
        "teams": teams,
        "metric_focus": metric_focus,
        "direction": direction,
        "window": "last5_vs_prev5",
        "scope": "team" if teams else "league",
        "threshold": threshold,
        "raw_question": raw_question,
        "requested_season": requested_season,
        "requested_season_type": requested_season_type,
        "requested_seasons": requested_seasons,
        "compare_kind": compare_kind,
        "wants_news": wants_news,
        "wants_news_impact": wants_impact,
        "wants_prediction": wants_prediction,
    }
