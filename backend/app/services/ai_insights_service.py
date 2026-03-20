from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.pulse_narrative import answer_for_route, build_chart_narrative, storyline_caption
from app.services.pulse_query_router import route_query
from app.services.pulse_llm import generate_smalltalk_response, rewrite_grounded_pulse_answer_with_meta
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
PULSE_INCLUDE_META = os.getenv("PULSE_INCLUDE_META", "1").strip().lower() not in {"0", "false", "no"}


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


def _stable_json_hash(payload: Dict[str, Any]) -> str:
    dumped = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return _stable_hash(dumped)


def _meta_payload(*, cache_status: str, provider: str = "none", fallback_used: bool = False, rewrite_applied: bool = False, source: str = "deterministic", note: str | None = None) -> Dict[str, Any]:
    meta = {
        "cache_status": cache_status,
        "provider": provider,
        "fallback_used": fallback_used,
        "rewrite_applied": rewrite_applied,
        "source": source,
    }
    if note:
        meta["note"] = note
    return meta


def _attach_meta(result: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    if PULSE_INCLUDE_META:
        result["meta"] = meta
    return result


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _round2(value: float) -> float:
    return round(float(value), 2)


def _confidence_band(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def _confidence_summary(label: str) -> str:
    if label == "high":
        return "Strong enough sample and signal alignment across the available stats."
    if label == "medium":
        return "Useful directional signal, but some context is limited or mixed."
    return "Limited support in the available data, so treat this as directional only."


def _compute_query_confidence(*, route: Dict[str, Any], items: List[Dict[str, Any]], team_filter: str | None = None) -> Dict[str, Any]:
    query_type = (route or {}).get("query_type") or "unknown"
    requested_teams = list((route or {}).get("teams") or [])
    requested_seasons = list((route or {}).get("seasons") or [])
    item_count = len(items or [])

    score = 0.35
    reasons: List[str] = []

    if query_type in {"team_trend", "team_compare", "stat_explain", "chart_explain"}:
        score += 0.10
        reasons.append("clear question type detected")

    if team_filter or requested_teams:
        score += 0.10
        reasons.append("team scope is specific")

    if requested_seasons:
        if len(requested_seasons) == 1:
            score += 0.08
            reasons.append("season is explicitly grounded")
        else:
            score += 0.04
            reasons.append("multiple seasons requested")

    if query_type == "team_compare":
        if len(requested_teams) >= 2 and item_count >= 2:
            score += 0.18
            reasons.append("both comparison teams resolved")
        else:
            score -= 0.10
            reasons.append("comparison scope is only partially resolved")
    elif query_type in {"team_trend", "stat_explain"}:
        if item_count >= 1:
            score += 0.18
            reasons.append("direct team summary available")
        else:
            score -= 0.12
            reasons.append("team summary is limited")
    elif query_type in {"league_rank", "league_trend", "trend_rank"}:
        if item_count >= 3:
            score += 0.14
            reasons.append("multiple league rows support the ranking")
        else:
            score -= 0.08
            reasons.append("ranking support is thin")
    elif query_type in {"smalltalk", "unknown", "clarify_team"}:
        score = 0.92
        reasons = ["response does not depend on sports stats"]

    completeness_values: List[float] = []
    metric_keys = [
        "recent_record",
        "margin_delta",
        "offense_delta",
        "defense_delta",
        "last5_avg_pf",
        "last5_avg_pa",
    ]
    for row in (items or [])[:4]:
        present = sum(1 for key in metric_keys if row.get(key) is not None)
        completeness_values.append(present / len(metric_keys))
    if completeness_values:
        completeness = sum(completeness_values) / len(completeness_values)
        score += (completeness - 0.5) * 0.24
        reasons.append(f"stat completeness {int(round(completeness * 100))}%")

    score = _clip01(score)
    label = _confidence_band(score)
    return {
        "score": _round2(score),
        "label": label,
        "summary": _confidence_summary(label),
        "reasons": reasons[:4],
    }


def _compute_chart_confidence(*, summary: Dict[str, Any], question: str) -> Dict[str, Any]:
    keys = [key for key, value in (summary or {}).items() if value is not None]
    count = len(keys)
    score = 0.42
    if count >= 6:
        score += 0.28
    elif count >= 3:
        score += 0.16
    else:
        score += 0.04

    q = (question or "").lower()
    if any(token in q for token in ["why", "trend", "stand out", "outlier", "compare"]):
        score += 0.08

    score = _clip01(score)
    label = _confidence_band(score)
    reasons = [f"chart summary includes {count} populated fields"]
    if count < 4:
        reasons.append("chart context is somewhat thin")
    return {
        "score": _round2(score),
        "label": label,
        "summary": _confidence_summary(label),
        "reasons": reasons[:3],
    }


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


def _merge_context_payload(
    *,
    page_context: Dict[str, Any] | None = None,
    chart_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    if page_context:
        merged["page_context"] = page_context
    if chart_context:
        merged["chart_context"] = chart_context
    return merged


def answer_chart_query(
    db: Session,
    *,
    chart_id: str,
    chart_title: str,
    sport: str,
    season: int,
    season_type: str,
    question: str,
    summary: Dict[str, Any],
    team_code: Optional[str] = None,
    page_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    sport = normalize_sport(sport)
    season_type = normalize_season_type(season_type)
    team_code = (team_code or "").upper().strip() or None
    question = (question or "").strip()

    if not question or not summary:
        return _attach_meta({
            "assistant_name": "Pulse",
            "answer": "Not enough data yet.",
            "supporting_items": [],
            "route": {"query_type": "chart_explain", "chart_id": chart_id, "chart_title": chart_title},
        }, _meta_payload(cache_status="skip", source="deterministic", note="missing-question-or-summary"))

    cache_key = f"ai:chart-query:v5:{sport}:{season}:{season_type}:{team_code or 'all'}:{chart_id}:{_stable_json_hash(summary)}:{_stable_hash(question.lower())}"
    cached = _cache_get(cache_key)
    if cached:
        try:
            payload = json.loads(cached)
            payload["meta"] = {**payload.get("meta", {}), "cache_status": "hit"}
            return payload
        except Exception:
            pass

    route = {
        "query_type": "chart_explain",
        "metric_focus": "overall",
        "direction": "neutral",
        "teams": [team_code] if team_code else [],
        "seasons": [season],
        "chart_id": chart_id,
        "chart_title": chart_title,
        "resolved_season": season,
        "resolved_season_type": season_type,
        "team_filter": team_code,
    }

    deterministic_answer = build_chart_narrative(
        chart_id=chart_id,
        chart_title=chart_title,
        sport=sport,
        season=season,
        season_type=season_type,
        team=team_code,
        summary=summary,
        question=question,
    )

    extra_context = _merge_context_payload(
        page_context=page_context,
        chart_context={
            "chart_id": chart_id,
            "chart_title": chart_title,
            "summary": summary,
        },
    )

    confidence = _compute_chart_confidence(summary=summary, question=question)

    rewritten, rewrite_meta = rewrite_grounded_pulse_answer_with_meta(
        question=question,
        sport=sport,
        season=season,
        season_type=season_type,
        route=route,
        items=[],
        deterministic_answer=deterministic_answer,
        extra_context={**extra_context, "confidence": confidence},
    )

    result = _attach_meta({
        "assistant_name": "Pulse",
        "answer": rewritten,
        "supporting_items": [],
        "route": route,
        "confidence": confidence,
    }, _meta_payload(
        cache_status="miss",
        provider=rewrite_meta.get("provider", "none"),
        fallback_used=bool(rewrite_meta.get("fallback_used")),
        rewrite_applied=bool(rewrite_meta.get("rewrite_applied")),
        source=rewrite_meta.get("source", "deterministic"),
        note=rewrite_meta.get("note"),
    ))
    _cache_set(cache_key, json.dumps(result), QUERY_TTL_SECONDS)
    return result


def answer_query(
    db: Session,
    *,
    sport: str,
    season: int,
    season_type: str,
    question: str,
    team_code: Optional[str] = None,
    page_context: Dict[str, Any] | None = None,
    chart_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    sport = normalize_sport(sport)
    base_season = int(season)
    base_season_type = normalize_season_type(season_type)
    team_code = (team_code or "").upper().strip() or None
    question = (question or "").strip()

    if not question:
        return _attach_meta({
            "assistant_name": "Pulse",
            "answer": "Ask a question about recent trends, team comparisons, rankings, or why a team is rising and falling.",
            "supporting_items": [],
            "storylines": [],
            "route": None,
            "confidence": {"score": 0.98, "label": "high", "summary": "No analytics claim was made.", "reasons": ["prompt is instructional only"]},
        }, _meta_payload(cache_status="skip", source="deterministic", note="empty-question"))

    pre_route = route_query(
        question=question,
        known_codes=set(),
        team_filter=team_code,
        default_season=base_season,
        default_season_type=base_season_type,
    )
    resolved_season = int(pre_route.get("requested_season") or base_season)
    resolved_season_type = normalize_season_type(pre_route.get("requested_season_type") or base_season_type)

    question_key = _stable_hash(question.lower())
    context_key = _stable_json_hash(_merge_context_payload(page_context=page_context, chart_context=chart_context))
    cache_key = f"ai:query:v8:{sport}:{resolved_season}:{resolved_season_type}:{team_code or 'all'}:{context_key}:{question_key}"
    cached = _cache_get(cache_key)
    if cached:
        try:
            payload = json.loads(cached)
            payload["meta"] = {**payload.get("meta", {}), "cache_status": "hit"}
            return payload
        except Exception:
            pass

    summaries = compute_league_trend_summaries(
        db,
        sport=sport,
        season=resolved_season,
        season_type=resolved_season_type,
        team_code=team_code,
    )
    if not summaries:
        return _attach_meta({
            "assistant_name": "Pulse",
            "answer": "Not enough data yet.",
            "supporting_items": [],
            "storylines": [],
            "route": {
                **pre_route,
                "resolved_season": resolved_season,
                "resolved_season_type": resolved_season_type,
                "team_filter": team_code,
            },
            "confidence": {"score": 0.28, "label": "low", "summary": "Limited support in the available data, so treat this as directional only.", "reasons": ["no season summaries were available"]},
        }, _meta_payload(cache_status="miss", source="deterministic", note="no-summaries"))

    known_codes = {s["team_code"] for s in summaries}
    route = route_query(
        question=question,
        known_codes=known_codes,
        team_filter=team_code,
        default_season=resolved_season,
        default_season_type=resolved_season_type,
    )
    route["resolved_season"] = resolved_season
    route["resolved_season_type"] = resolved_season_type
    route["team_filter"] = team_code
    if page_context:
        route["page_context"] = page_context
    if chart_context:
        route["chart_context"] = chart_context

    context = _build_query_context(summaries, route=route)
    items = context.get("items") or []

    if route["query_type"] in {"smalltalk", "unknown"}:
        result = _attach_meta({
            "assistant_name": "Pulse",
            "answer": generate_smalltalk_response(question),
            "supporting_items": [],
            "storylines": [],
            "route": route,
            "confidence": {"score": 0.96, "label": "high", "summary": "No stat-based claim was required for this reply.", "reasons": ["small-talk response only"]},
        }, _meta_payload(cache_status="miss", source="deterministic", note="smalltalk"))
        _cache_set(cache_key, json.dumps(result), QUERY_TTL_SECONDS)
        return result

    if route["query_type"] == "clarify_team":
        result = _attach_meta({
            "assistant_name": "Pulse",
            "answer": route.get("message") or "Which team are you asking about?",
            "supporting_items": [],
            "storylines": [],
            "route": route,
            "confidence": {"score": 0.95, "label": "high", "summary": "Pulse is waiting for a clearer target before making an analytics claim.", "reasons": ["team resolution needs clarification"]},
        }, _meta_payload(cache_status="miss", source="deterministic", note="clarify-team"))
        _cache_set(cache_key, json.dumps(result), QUERY_TTL_SECONDS)
        return result

    if route["query_type"] in {"team_trend", "stat_explain"} and route.get("teams"):
        direct = compute_team_trend_summary(
            db,
            sport=sport,
            season=resolved_season,
            season_type=resolved_season_type,
            team_code=route["teams"][0],
        )
        if direct:
            items = [direct]
            context["items"] = items

    storylines = build_storylines(
        db,
        sport=sport,
        season=resolved_season,
        season_type=resolved_season_type,
        team_code=team_code,
        limit=4,
    )
    deterministic_answer = answer_for_route(route, context, sport)
    if not deterministic_answer:
        deterministic_answer = _fallback_answer(context, route)

    confidence = _compute_query_confidence(route=route, items=items, team_filter=team_code)

    rewritten, rewrite_meta = rewrite_grounded_pulse_answer_with_meta(
        question=question,
        sport=sport,
        season=resolved_season,
        season_type=resolved_season_type,
        route=route,
        items=items,
        deterministic_answer=deterministic_answer,
        extra_context={**_merge_context_payload(page_context=page_context, chart_context=chart_context), "confidence": confidence},
    )

    result = _attach_meta({
        "assistant_name": "Pulse",
        "answer": rewritten,
        "supporting_items": items[:5],
        "storylines": storylines,
        "route": route,
        "confidence": confidence,
    }, _meta_payload(
        cache_status="miss",
        provider=rewrite_meta.get("provider", "none"),
        fallback_used=bool(rewrite_meta.get("fallback_used")),
        rewrite_applied=bool(rewrite_meta.get("rewrite_applied")),
        source=rewrite_meta.get("source", "deterministic"),
        note=rewrite_meta.get("note"),
    ))
    _cache_set(cache_key, json.dumps(result), QUERY_TTL_SECONDS)
    return result
