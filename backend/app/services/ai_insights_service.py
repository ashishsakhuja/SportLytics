from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.pulse_narrative import answer_for_route, storyline_caption
from app.services.pulse_query_router import route_query
from app.services.pulse_llm import generate_smalltalk_response, rewrite_grounded_pulse_answer
from app.services.pulse_trend_engine import (
    compute_league_trend_summaries,
    compute_team_trend_summary,
    normalize_season_type,
    normalize_sport,
)
from app.services.redis_cache import get_redis

POINTS_LABEL = {"nfl": "points", "nba": "points", "mlb": "runs", "nhl": "goals"}
QUERY_TTL_SECONDS = int(os.getenv("AI_QUERY_TTL_SECONDS", "900"))
STORYLINES_TTL_SECONDS = int(os.getenv("AI_STORYLINES_TTL_SECONDS", "900"))


def _cache_get(key: str) -> Optional[str]:
    r = get_redis()
    if r is None:
        return None
    try:
        r.ping()
        return r.get(key)
    except Exception:
        return None


def _cache_set(key: str, value: str, ttl: int) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.ping()
        r.setex(key, ttl, value)
    except Exception:
        return


def _stable_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def build_team_summaries(
    db: Session,
    *,
    sport: str,
    season: int,
    season_type: str,
    team_code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return compute_league_trend_summaries(
        db,
        sport=sport,
        season=season,
        season_type=season_type,
        team_code=team_code,
    )


def _sort_rows(rows: List[Dict[str, Any]], metric_focus: str, direction: str) -> List[Dict[str, Any]]:
    def value(row: Dict[str, Any]) -> float:
        if metric_focus == "offense":
            return float(row.get("offense_delta") or -9999)
        if metric_focus == "defense":
            return float(row.get("defense_delta") or -9999)
        if metric_focus == "turnovers":
            return float(row.get("turnover_delta") or -9999)
        if metric_focus == "split":
            return abs(float(row.get("home_away_gap") or -9999))
        if metric_focus == "sos":
            return float(row.get("recent_sos") or -9999)
        if metric_focus == "margin":
            return float(row.get("margin_delta") or -9999)

        score = 0.0
        for key in ("margin_delta", "offense_delta", "defense_delta", "turnover_delta"):
            score += abs(float(row.get(key) or 0.0))
        return score

    reverse = direction != "down"
    return sorted(rows, key=value, reverse=reverse)


def _build_storyline_candidates(summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    valid_offense = [s for s in summaries if s.get("offense_delta") is not None]
    valid_defense = [s for s in summaries if s.get("defense_delta") is not None]
    valid_margin = [s for s in summaries if s.get("margin_delta") is not None]
    valid_split = [s for s in summaries if s.get("home_away_gap") is not None]
    valid_turnovers = [s for s in summaries if s.get("turnover_delta") is not None]
    valid_sos = [s for s in summaries if s.get("sos_delta") is not None]

    candidates: List[Dict[str, Any]] = []

    def pick(sorted_rows: List[Dict[str, Any]], category: str, title: str, direction: str, value_key: str):
        if not sorted_rows:
            return
        row = sorted_rows[0]
        candidates.append(
            {
                "id": f"{row['team_code'].lower()}-{category}-{direction}",
                "title": title.format(team=row["label"]),
                "team_code": row["team_code"],
                "team_label": row["label"],
                "category": category,
                "direction": direction,
                "metric_value": row.get(value_key),
                "support": {
                    "recent_record": row.get("recent_record"),
                    "games": row.get("games"),
                    "season_avg_margin": row.get("season_avg_margin"),
                    "last5_avg_margin": row.get("last5_avg_margin"),
                    "prev5_avg_margin": row.get("prev5_avg_margin"),
                    "last5_avg_pf": row.get("last5_avg_pf"),
                    "prev5_avg_pf": row.get("prev5_avg_pf"),
                    "last5_avg_pa": row.get("last5_avg_pa"),
                    "prev5_avg_pa": row.get("prev5_avg_pa"),
                    "last5_avg_turnovers": row.get("last5_avg_turnovers"),
                    "prev5_avg_turnovers": row.get("prev5_avg_turnovers"),
                    "home_avg_margin": row.get("home_avg_margin"),
                    "away_avg_margin": row.get("away_avg_margin"),
                    "recent_sos": row.get("recent_sos"),
                    "season_sos": row.get("season_sos"),
                    value_key: row.get(value_key),
                },
            }
        )

    pick(sorted(valid_offense, key=lambda x: x["offense_delta"], reverse=True), "offense", "{team} offense heating up", "up", "offense_delta")
    pick(sorted(valid_defense, key=lambda x: x["defense_delta"], reverse=True), "defense", "{team} tightening up defensively", "up", "defense_delta")
    pick(sorted(valid_margin, key=lambda x: x["margin_delta"], reverse=True), "margin", "{team} winning the recent form battle", "up", "margin_delta")
    pick(sorted(valid_margin, key=lambda x: x["margin_delta"]), "margin", "{team} losing ground recently", "down", "margin_delta")
    pick(sorted(valid_turnovers, key=lambda x: x["turnover_delta"], reverse=True), "turnovers", "{team} cleaning up the turnover battle", "up", "turnover_delta")
    pick(sorted(valid_sos, key=lambda x: x["sos_delta"], reverse=True), "sos", "{team} facing a tougher recent slate", "up", "sos_delta")
    pick(sorted(valid_split, key=lambda x: abs(x["home_away_gap"]), reverse=True), "split", "{team} showing a strong location split", "split", "home_away_gap")
    return candidates


def build_storylines(
    db: Session,
    *,
    sport: str,
    season: int,
    season_type: str,
    team_code: Optional[str] = None,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    sport = normalize_sport(sport)
    season_type = normalize_season_type(season_type)
    team_code = (team_code or "").upper().strip() or None

    cache_key = f"ai:storylines:{sport}:{season}:{season_type}:{team_code or 'all'}:{limit}"
    cached = _cache_get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass

    summaries = compute_league_trend_summaries(db, sport=sport, season=season, season_type=season_type, team_code=team_code)
    if not summaries:
        return []

    candidates = _build_storyline_candidates(summaries)
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for item in candidates:
        if item["id"] in seen or len(out) >= limit:
            continue
        seen.add(item["id"])
        item["caption"] = storyline_caption(item, sport)
        out.append(item)

    _cache_set(cache_key, json.dumps(out), STORYLINES_TTL_SECONDS)
    return out


def _build_query_context(
    summaries: List[Dict[str, Any]],
    *,
    route: Dict[str, Any],
) -> Dict[str, Any]:
    query_type = route["query_type"]
    teams = route.get("teams") or []
    metric_focus = route.get("metric_focus", "overall")
    direction = route.get("direction", "neutral")

    if query_type == "team_compare":
        selected = [s for s in summaries if s["team_code"] in teams][:2]
        return {"mode": "team_compare", "items": selected}

    if query_type in {"team_trend", "stat_explain"}:
        selected = [s for s in summaries if s["team_code"] in teams] if teams else summaries[:1]
        return {"mode": query_type, "items": selected[:2]}

    if query_type in {"smalltalk", "unknown", "clarify_team"}:
        return {"mode": query_type, "items": []}

    sorted_rows = _sort_rows(summaries, metric_focus, direction)
    return {
        "mode": query_type,
        "metric_focus": metric_focus,
        "direction": direction,
        "items": sorted_rows[:5],
    }


def _fallback_answer(context: Dict[str, Any], route: Dict[str, Any]) -> str:
    items = context.get("items") or []
    if not items:
        return "Not enough data yet."

    if route["query_type"] == "team_compare" and len(items) >= 2:
        a, b = items[0], items[1]
        return (
            f"{a['label']} vs {b['label']}: recent margin delta is {a.get('margin_delta')} versus {b.get('margin_delta')}, "
            f"offense delta is {a.get('offense_delta')} versus {b.get('offense_delta')}, and defense delta is {a.get('defense_delta')} versus {b.get('defense_delta')}."
        )

    if route["query_type"] == "team_trend":
        row = items[0]
        return (
            f"{row['label']} is {row.get('recent_record')} in its last five. "
            f"Its recent margin is {row.get('last5_avg_margin')} versus {row.get('prev5_avg_margin')} in the previous five, "
            f"with offense delta {row.get('offense_delta')} and defense delta {row.get('defense_delta')}."
        )

    top = items[:3]
    return "Top signals: " + ", ".join(
        f"{row['team_code']} (margin Δ {row.get('margin_delta')}, offense Δ {row.get('offense_delta')}, defense Δ {row.get('defense_delta')})"
        for row in top
    )


def answer_query(
    db: Session,
    *,
    sport: str,
    season: int,
    season_type: str,
    question: str,
    team_code: Optional[str] = None,
) -> Dict[str, Any]:
    sport = normalize_sport(sport)
    season_type = normalize_season_type(season_type)
    team_code = (team_code or "").upper().strip() or None
    question = (question or "").strip()

    if not question:
        return {
            "assistant_name": "Pulse",
            "answer": "Ask a question about recent trends, team comparisons, rankings, or why a team is rising and falling.",
            "supporting_items": [],
            "storylines": [],
            "route": None,
        }

    question_key = _stable_hash(question.lower())
    cache_key = f"ai:query:v3:{sport}:{season}:{season_type}:{team_code or 'all'}:{question_key}"
    cached = _cache_get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass

    summaries = compute_league_trend_summaries(
        db,
        sport=sport,
        season=season,
        season_type=season_type,
        team_code=team_code,
    )
    if not summaries:
        return {
            "assistant_name": "Pulse",
            "answer": "Not enough data yet.",
            "supporting_items": [],
            "storylines": [],
            "route": None,
        }

    known_codes = {s["team_code"] for s in summaries}
    route = route_query(question=question, known_codes=known_codes, team_filter=team_code)
    context = _build_query_context(summaries, route=route)
    items = context.get("items") or []

    if route["query_type"] in {"smalltalk", "unknown"}:
        result = {
            "assistant_name": "Pulse",
            "answer": generate_smalltalk_response(question),
            "supporting_items": [],
            "storylines": [],
            "route": route,
        }
        _cache_set(cache_key, json.dumps(result), QUERY_TTL_SECONDS)
        return result

    if route["query_type"] == "clarify_team":
        result = {
            "assistant_name": "Pulse",
            "answer": route.get("message") or "Which team are you asking about?",
            "supporting_items": [],
            "storylines": [],
            "route": route,
        }
        _cache_set(cache_key, json.dumps(result), QUERY_TTL_SECONDS)
        return result

    if route["query_type"] in {"team_trend", "stat_explain"} and route.get("teams"):
        direct = compute_team_trend_summary(
            db,
            sport=sport,
            season=season,
            season_type=season_type,
            team_code=route["teams"][0],
        )
        if direct:
            items = [direct]
            context["items"] = items

    storylines = build_storylines(
        db,
        sport=sport,
        season=season,
        season_type=season_type,
        team_code=team_code,
        limit=4,
    )
    answer = answer_for_route(route, context, sport)
    if not answer:
        answer = _fallback_answer(context, route)

    answer = rewrite_grounded_pulse_answer(
        question=question,
        sport=sport,
        season=season,
        season_type=season_type,
        route=route,
        items=items,
        deterministic_answer=answer,
    )

    result = {
        "assistant_name": "Pulse",
        "answer": answer,
        "supporting_items": items[:5],
        "storylines": storylines,
        "route": route,
    }
    _cache_set(cache_key, json.dumps(result), QUERY_TTL_SECONDS)
    return result
