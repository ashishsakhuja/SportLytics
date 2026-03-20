from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import ContentItem
from app.services.team_aliases import TEAM_ALIASES

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
PREDICTION_DISCLAIMER = (
    "Prediction note: this is a trend-based estimate using recent SportLytics data, not a guarantee or betting advice."
)
INJURY_HINTS = (
    "injury", "injuries", "questionable", "doubtful", "out", "inactive", "ir", "day-to-day", "sidelined",
    "limited", "game-time decision", "concussion", "hamstring", "ankle", "knee", "wrist", "illness",
    "suspended", "suspension", "unavailable", "placed on injured reserve", "scratched", "absence", "absent"
)

TRADE_TERMS = (
    "trade", "traded", "acquired", "acquire", "deal", "dealt", "waived", "released", "signed", "signs",
    "activates", "activated", "recalls", "recalled", "promoted", "called up", "returns", "returning", "back in the lineup"
)

OFFENSE_HINTS = {
    "qb", "quarterback", "rb", "wr", "receiver", "tight end", "lineman", "offense", "offensive",
    "scorer", "scores", "goal scorer", "top scorer", "shot creator", "playmaker", "guard", "forward",
    "bat", "batter", "hitter", "slugger", "lineup", "starter", "points", "goals", "runs"
}

DEFENSE_HINTS = {
    "defense", "defensive", "corner", "cornerback", "safety", "linebacker", "pass rusher", "edge",
    "goalie", "goaltender", "defenseman", "center back", "pitcher", "rotation", "bullpen", "closer",
    "rim protector", "rebounder", "stops", "blocks", "saves"
}


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


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


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
                    "season_avg_pf": row.get("season_avg_pf"),
                    "last5_avg_pf": row.get("last5_avg_pf"),
                    "prev5_avg_pf": row.get("prev5_avg_pf"),
                    "season_avg_pa": row.get("season_avg_pa"),
                    "last5_avg_pa": row.get("last5_avg_pa"),
                    "prev5_avg_pa": row.get("prev5_avg_pa"),
                    "offense_delta": row.get("offense_delta"),
                    "defense_delta": row.get("defense_delta"),
                    "turnover_delta": row.get("turnover_delta"),
                    "home_away_gap": row.get("home_away_gap"),
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

    if query_type in {"team_trend", "stat_explain", "predictive"}:
        selected = [s for s in summaries if s["team_code"] in teams] if teams else summaries[:5]
        return {"mode": query_type, "items": selected[:5]}

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


def _confidence_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    games = int(row.get("games") or 0)
    recent = _safe_float(row.get("last5_avg_margin")) or 0.0
    previous = _safe_float(row.get("prev5_avg_margin")) or 0.0
    season = _safe_float(row.get("season_avg_margin")) or 0.0
    consistency_bonus = 0.1 if (recent >= 0 and season >= 0) or (recent < 0 and season < 0) else 0.0
    stability_bonus = 0.1 if abs(recent - previous) <= 4 else 0.0
    sample_bonus = min(0.15, games / 100.0)
    raw = max(0.38, min(0.84, 0.44 + consistency_bonus + stability_bonus + sample_bonus))
    label = "low" if raw < 0.52 else ("medium" if raw < 0.68 else "high")
    return {"score": round(raw, 2), "label": label}


def _project_row_forward(row: Dict[str, Any]) -> Dict[str, Any]:
    last5_pf = _safe_float(row.get("last5_avg_pf"))
    prev5_pf = _safe_float(row.get("prev5_avg_pf"))
    season_pf = _safe_float(row.get("season_avg_pf"))
    last5_pa = _safe_float(row.get("last5_avg_pa"))
    prev5_pa = _safe_float(row.get("prev5_avg_pa"))
    season_pa = _safe_float(row.get("season_avg_pa"))
    last5_margin = _safe_float(row.get("last5_avg_margin"))
    prev5_margin = _safe_float(row.get("prev5_avg_margin"))
    season_margin = _safe_float(row.get("season_avg_margin"))
    recent_sos = _safe_float(row.get("recent_sos"))
    season_sos = _safe_float(row.get("season_sos"))

    def blend(last5: Optional[float], season: Optional[float], prev5: Optional[float]) -> Optional[float]:
        vals = [v for v in [last5, season, prev5] if v is not None]
        if not vals:
            return None
        if last5 is None:
            return _round(sum(vals) / len(vals))
        return _round(0.55 * (last5 or 0.0) + 0.30 * (season or last5 or 0.0) + 0.15 * (prev5 or season or last5 or 0.0))

    base_pf = blend(last5_pf, season_pf, prev5_pf)
    base_pa = blend(last5_pa, season_pa, prev5_pa)
    base_margin = blend(last5_margin, season_margin, prev5_margin)

    sos_adjust = 0.0
    if recent_sos is not None and season_sos is not None:
        sos_adjust = max(-1.5, min(1.5, (season_sos - recent_sos) * 8.0))

    projected_pf = _round((base_pf or 0.0) + sos_adjust) if base_pf is not None else None
    projected_pa = _round((base_pa or 0.0) - sos_adjust) if base_pa is not None else None
    projected_margin = _round((base_margin or 0.0) + sos_adjust) if base_margin is not None else None

    confidence = _confidence_from_row(row)
    return {
        "team_code": row.get("team_code"),
        "team_label": row.get("label") or row.get("team_code"),
        "projected_pf": projected_pf,
        "projected_pa": projected_pa,
        "projected_margin": projected_margin,
        "confidence": confidence,
    }


def _build_generated_plot(
    *,
    route: Dict[str, Any],
    sport: str,
    season: int,
    season_type: str,
    items: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not items:
        return None

    metric_focus = route.get("metric_focus") or "overall"
    query_type = route.get("query_type")
    stat_word = POINTS_LABEL.get(sport, "points")

    if query_type == "team_trend":
        row = items[0]
        return {
            "chart_id": f"pulse-trend-{sport}-{row['team_code'].lower()}",
            "title": f"{row['label']} recent trend snapshot",
            "subtitle": f"Previous five vs last five {stat_word} and margin",
            "kind": "bar",
            "data": [
                {"label": "Previous 5", "Offense": row.get("prev5_avg_pf"), "Defense Allowed": row.get("prev5_avg_pa"), "Margin": row.get("prev5_avg_margin")},
                {"label": "Last 5", "Offense": row.get("last5_avg_pf"), "Defense Allowed": row.get("last5_avg_pa"), "Margin": row.get("last5_avg_margin")},
            ],
            "series": [
                {"key": "Offense", "label": "Offense"},
                {"key": "Defense Allowed", "label": "Defense Allowed"},
                {"key": "Margin", "label": "Margin"},
            ],
            "share_body": f"Pulse generated a recent trend view for {row['label']} on SportLytics. Curious whether everyone else sees the same momentum here.",
        }

    if query_type == "team_compare" and len(items) >= 2:
        a, b = items[0], items[1]
        return {
            "chart_id": f"pulse-compare-{sport}-{a['team_code'].lower()}-{b['team_code'].lower()}",
            "title": f"{a['team_code']} vs {b['team_code']} recent comparison",
            "subtitle": "Last-five performance and trend deltas",
            "kind": "bar",
            "data": [
                {"label": a["team_code"], "Last 5 Offense": a.get("last5_avg_pf"), "Margin Delta": a.get("margin_delta"), "Defense Delta": a.get("defense_delta")},
                {"label": b["team_code"], "Last 5 Offense": b.get("last5_avg_pf"), "Margin Delta": b.get("margin_delta"), "Defense Delta": b.get("defense_delta")},
            ],
            "series": [
                {"key": "Last 5 Offense", "label": "Last 5 Offense"},
                {"key": "Margin Delta", "label": "Margin Delta"},
                {"key": "Defense Delta", "label": "Defense Delta"},
            ],
            "share_body": f"Pulse built a head-to-head comparison for {a['label']} and {b['label']} based on recent SportLytics form.",
        }

    if query_type in {"league_rank", "trend_rank"}:
        top = items[:5]
        if metric_focus == "defense":
            series_key = "Defense Delta"
            data = [{"label": row["team_code"], series_key: row.get("defense_delta")} for row in top]
        elif metric_focus == "offense":
            series_key = "Offense Delta"
            data = [{"label": row["team_code"], series_key: row.get("offense_delta")} for row in top]
        else:
            series_key = "Margin Delta"
            data = [{"label": row["team_code"], series_key: row.get("margin_delta")} for row in top]
        return {
            "chart_id": f"pulse-rank-{sport}-{metric_focus}",
            "title": f"Pulse top recent movers — {metric_focus.title()}",
            "subtitle": f"Top 5 by recent {metric_focus} signal",
            "kind": "bar",
            "data": data,
            "series": [{"key": series_key, "label": series_key}],
            "share_body": f"Pulse surfaced the top recent {metric_focus} movers from the {sport.upper()} dashboard.",
        }

    if query_type == "predictive":
        row = items[0]
        forecast = _project_row_forward(row)
        return {
            "chart_id": f"pulse-forecast-{sport}-{row['team_code'].lower()}",
            "title": f"{row['label']} forward outlook",
            "subtitle": "Season baseline, recent form, and next-step estimate",
            "kind": "line",
            "data": [
                {"label": "Previous 5", "Offense": row.get("prev5_avg_pf"), "Defense Allowed": row.get("prev5_avg_pa"), "Margin": row.get("prev5_avg_margin")},
                {"label": "Season Avg", "Offense": row.get("season_avg_pf"), "Defense Allowed": row.get("season_avg_pa"), "Margin": row.get("season_avg_margin")},
                {"label": "Last 5", "Offense": row.get("last5_avg_pf"), "Defense Allowed": row.get("last5_avg_pa"), "Margin": row.get("last5_avg_margin")},
                {"label": "Forecast", "Offense": forecast.get("projected_pf"), "Defense Allowed": forecast.get("projected_pa"), "Margin": forecast.get("projected_margin")},
            ],
            "series": [
                {"key": "Offense", "label": "Offense"},
                {"key": "Defense Allowed", "label": "Defense Allowed"},
                {"key": "Margin", "label": "Margin"},
            ],
            "share_body": f"Pulse generated a forward outlook for {row['label']}. It is trend-based rather than guaranteed, but it is a useful discussion starter.",
        }

    return None


def _answer_predictive(route: Dict[str, Any], sport: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    stat_word = POINTS_LABEL.get(sport, "points")
    threshold = route.get("threshold")

    if route.get("teams"):
        row = items[0] if items else None
        if not row:
            return {"answer": "Not enough data yet.", "prediction": None}
        forecast = _project_row_forward(row)
        confidence = forecast["confidence"]
        phrasing = "hold its level" if (forecast.get("projected_margin") or 0) >= 0 else "face some regression risk"
        answer = (
            f"My trend-based read is that {forecast['team_label']} should {phrasing} in the near future. "
            f"Its blended forecast comes out to about {forecast.get('projected_pf')} {stat_word} scored, {forecast.get('projected_pa')} allowed, "
            f"and a projected margin around {forecast.get('projected_margin')}. "
            f"Confidence is {confidence['label']} ({confidence['score']}). {PREDICTION_DISCLAIMER}"
        )
        return {"answer": answer, "prediction": forecast}

    ranked: List[Dict[str, Any]] = []
    for row in items[:5]:
        forecast = _project_row_forward(row)
        row_copy = dict(row)
        row_copy.update({"prediction": forecast})
        ranked.append(row_copy)

    if threshold is not None and ranked:
        filtered = [r for r in ranked if (_safe_float((r.get("prediction") or {}).get("projected_pf")) or -999) >= float(threshold)] or ranked
        parts = [
            f"{r['team_code']} at {_round((r.get('prediction') or {}).get('projected_pf'))} projected {stat_word}"
            for r in filtered[:4]
        ]
        answer = (
            f"Based on recent form blended with season baseline, the strongest candidates to clear {threshold:.0f} {stat_word} next time out are "
            + "; ".join(parts)
            + f". {PREDICTION_DISCLAIMER}"
        )
        return {"answer": answer, "prediction": {"ranked": [{"team_code": r["team_code"], **(r.get("prediction") or {})} for r in filtered[:5]]}}

    top = ranked[:4]
    answer = (
        "The teams with the strongest forward momentum right now are "
        + "; ".join(
            f"{r['team_code']} (projected margin {_round((r.get('prediction') or {}).get('projected_margin'))}, confidence {(r.get('prediction') or {}).get('confidence', {}).get('label', 'medium')})"
            for r in top
        )
        + f". {PREDICTION_DISCLAIMER}"
    )
    return {"answer": answer, "prediction": {"ranked": [{"team_code": r["team_code"], **(r.get("prediction") or {})} for r in top]}}




def _news_aliases_for_codes(team_codes: List[str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for code in team_codes:
        aliases = [alias for alias, mapped in TEAM_ALIASES.items() if mapped == code]
        aliases.extend([code, code.lower()])
        # preserve order, trim long alias sets
        uniq: List[str] = []
        for a in aliases:
            a = str(a or '').strip()
            if a and a.lower() not in {x.lower() for x in uniq}:
                uniq.append(a)
        out[code] = uniq[:12]
    return out


def _contains_phrase(text: str, phrases: tuple[str, ...] | set[str]) -> bool:
    return any(p in text for p in phrases)


def _news_side_of_ball(hay: str) -> str:
    offense_hits = sum(1 for term in OFFENSE_HINTS if term in hay)
    defense_hits = sum(1 for term in DEFENSE_HINTS if term in hay)
    if offense_hits and defense_hits:
        return "both"
    if offense_hits:
        return "offense"
    if defense_hits:
        return "defense"
    return "overall"


def _news_move_type(hay: str) -> str:
    if any(term in hay for term in ("suspended", "suspension", "ruled out", "out for season")):
        return "absence"
    if any(term in hay for term in ("questionable", "doubtful", "day-to-day", "game-time decision", "limited")):
        return "uncertain"
    if any(term in hay for term in ("returns", "returning", "activated", "back in the lineup", "cleared", "reinstated")):
        return "return"
    if any(term in hay for term in ("trade", "traded", "acquired", "dealt", "waived", "released", "signed", "promoted", "recalled")):
        return "transaction"
    if _contains_phrase(hay, INJURY_HINTS):
        return "injury"
    return "news"


def _estimate_news_item_impact(item: ContentItem) -> Dict[str, Any]:
    title = str(item.title or '').strip()
    snippet = str(item.summary or item.snippet or '').strip()
    hay = f"{title} {snippet}".lower()

    side = _news_side_of_ball(hay)
    move_type = _news_move_type(hay)

    direction = "neutral"
    score = 0.0
    tags: List[str] = []

    severe_negative = any(term in hay for term in ("out for season", "torn", "surgery", "suspended", "placed on injured reserve", "ruled out"))
    medium_negative = _contains_phrase(hay, INJURY_HINTS) or any(term in hay for term in ("waived", "released", "traded away", "dealt away"))
    positive_return = any(term in hay for term in ("returns", "returning", "activated", "back in the lineup", "cleared", "reinstated"))
    positive_add = any(term in hay for term in ("acquired", "trade for", "traded for", "signed", "recalls", "recalled", "promoted", "called up"))
    uncertain = any(term in hay for term in ("questionable", "doubtful", "day-to-day", "game-time decision", "limited"))

    if severe_negative:
        direction = "negative"
        score = 1.6
        tags.append("major absence risk")
    elif medium_negative:
        direction = "negative"
        score = 1.0
        tags.append("availability concern")

    if uncertain:
        if score < 0.8:
            score = 0.8
        if direction == "neutral":
            direction = "negative"
        tags.append("uncertain status")

    if positive_return:
        direction = "positive"
        score = max(score, 1.0 if move_type == "return" else 0.8)
        tags.append("return boost")

    if positive_add:
        if "waived" in hay or "released" in hay:
            direction = "negative"
            score = max(score, 0.8)
        else:
            direction = "positive"
            score = max(score, 0.9)
        tags.append("roster move")

    if any(term in hay for term in ("trade", "traded", "acquired", "dealt")) and "roster move" not in tags:
        tags.append("roster move")

    if move_type in {"injury", "absence", "uncertain"} and "injury watch" not in tags:
        tags.append("injury watch")

    if side == "offense":
        tags.append("offense signal")
    elif side == "defense":
        tags.append("defense signal")
    elif side == "both":
        tags.append("two-way signal")

    summary = "General recent headline."
    if direction == "negative":
        summary = f"Possible downside from {move_type.replace('_', ' ')} news"
    elif direction == "positive":
        summary = f"Possible lift from {move_type.replace('_', ' ')} news"
    elif uncertain:
        summary = "Status uncertainty could matter"

    return {
        "impact_tags": list(dict.fromkeys(tags)),
        "impact_score": _round(score, 2) or 0.0,
        "impact_direction": direction,
        "move_type": move_type,
        "side_of_ball": side,
        "impact_summary": summary,
    }


def _build_news_impact_profile(related_news: List[Dict[str, Any]]) -> Dict[str, Any]:
    profile = {
        "offense_delta": 0.0,
        "defense_delta": 0.0,
        "margin_delta": 0.0,
        "confidence_penalty": 0.0,
        "volatility": 0.0,
        "reasons": [],
    }
    for item in related_news:
        score = _safe_float(item.get("impact_score")) or 0.0
        direction = str(item.get("impact_direction") or "neutral")
        side = str(item.get("side_of_ball") or "overall")
        move_type = str(item.get("move_type") or "news")
        sign = 1.0 if direction == "positive" else (-1.0 if direction == "negative" else 0.0)
        scaled = min(1.8, score)

        if side in {"offense", "both"}:
            profile["offense_delta"] += sign * scaled
        if side in {"defense", "both"}:
            profile["defense_delta"] += sign * scaled
        if side == "overall":
            profile["margin_delta"] += sign * scaled * 0.7

        # volatility and confidence penalties rise with uncertain availability and transactions
        if move_type in {"injury", "absence", "uncertain", "transaction"}:
            profile["confidence_penalty"] += min(0.05, score * 0.03)
            profile["volatility"] += min(0.25, score * 0.12)

        if sign != 0 and len(profile["reasons"]) < 4:
            profile["reasons"].append(str(item.get("impact_summary") or item.get("title") or "headline factor"))

    for key in ("offense_delta", "defense_delta", "margin_delta"):
        profile[key] = max(-3.0, min(3.0, round(profile[key], 2)))
    profile["confidence_penalty"] = round(min(0.14, profile["confidence_penalty"]), 2)
    profile["volatility"] = round(min(0.6, profile["volatility"]), 2)
    return profile


def _serialize_news_item(item: ContentItem) -> Dict[str, Any]:
    title = str(item.title or '').strip()
    snippet = str(item.summary or item.snippet or '').strip()
    impact = _estimate_news_item_impact(item)
    return {
        'id': item.id,
        'title': title,
        'source': item.source,
        'sport': item.sport,
        'published_at': item.published_at.isoformat() if item.published_at else None,
        'url': item.url,
        'snippet': snippet[:260] if snippet else None,
        **impact,
    }


def _fetch_related_news(db: Session, *, sport: str, route: Dict[str, Any], team_code: Optional[str], limit: int = 5) -> List[Dict[str, Any]]:
    teams = list(dict.fromkeys((route.get('teams') or []) + ([team_code] if team_code else [])))
    query = db.query(ContentItem).filter(ContentItem.sport == sport).order_by(ContentItem.published_at.desc())

    if teams:
        alias_map = _news_aliases_for_codes(teams)
        conditions = []
        for code, aliases in alias_map.items():
            try:
                conditions.append(ContentItem.teams.any(code))
            except Exception:
                pass
            for alias in aliases:
                like = f"%{alias}%"
                conditions.extend([
                    ContentItem.team.ilike(like),
                    ContentItem.title.ilike(like),
                    ContentItem.snippet.ilike(like),
                    ContentItem.summary.ilike(like),
                ])
        if conditions:
            query = query.filter(sa.or_(*conditions))

    rows = query.limit(max(1, min(8, limit))).all()
    return [_serialize_news_item(row) for row in rows]


def _build_news_summary_answer(route: Dict[str, Any], items: List[Dict[str, Any]], related_news: List[Dict[str, Any]]) -> str:
    if not related_news:
        return 'I could not find enough recent news context for that team or league view yet.'
    prefix = 'Here are the biggest recent headlines I found'
    if route.get('teams'):
        prefix = f"Here are the main recent headlines around {route['teams'][0]}"
    bullets = []
    for n in related_news[:3]:
        bits = [n['title']]
        if n.get('impact_tags'):
            bits.append(f"({', '.join(n['impact_tags'])})")
        if n.get('source'):
            bits.append(f"— {n['source']}")
        bullets.append(' '.join(bits))
    answer = prefix + ': ' + '; '.join(bullets) + '.'
    if items:
        row = items[0]
        answer += (
            f" In the numbers, the current trend snapshot still has {row.get('label') or row.get('team_code')} at "
            f"{row.get('recent_record')} lately with margin Δ {row.get('margin_delta')}."
        )
    return answer


def _build_news_impact_answer(route: Dict[str, Any], items: List[Dict[str, Any]], related_news: List[Dict[str, Any]], sport: str) -> str:
    if not items:
        return _build_news_summary_answer(route, items, related_news)
    row = items[0]
    stat_word = POINTS_LABEL.get(sport, 'points')
    trend_piece = (
        f"In the game data, the recent shift is from {row.get('prev5_avg_pf')} to {row.get('last5_avg_pf')} {stat_word} scored "
        f"and from {row.get('prev5_avg_pa')} to {row.get('last5_avg_pa')} allowed."
    )
    if not related_news:
        return f"I can explain the historical trend, but I did not find enough recent injury or roster context yet. {trend_piece}"
    profile = _build_news_impact_profile(related_news)
    drivers = '; '.join(str(x) for x in (profile.get('reasons') or [])[:3])
    return (
        "The news matters here because availability and roster movement can shift how we interpret the recent sample. "
        + trend_piece
        + f" My lightweight impact layer reads those headlines as roughly offense {profile.get('offense_delta', 0):+}, defense {profile.get('defense_delta', 0):+}, "
        + f"with added volatility {profile.get('volatility', 0)}. Relevant drivers: {drivers}."
    )


def _apply_news_to_prediction(prediction: Dict[str, Any], related_news: List[Dict[str, Any]]) -> Dict[str, Any]:
    adjusted = dict(prediction or {})
    profile = _build_news_impact_profile(related_news)
    adjusted['news_adjustment'] = 'none'
    adjusted['news_profile'] = profile
    if not related_news:
        return adjusted

    offense_delta = float(profile.get('offense_delta') or 0.0)
    defense_delta = float(profile.get('defense_delta') or 0.0)
    margin_delta = float(profile.get('margin_delta') or 0.0)

    if adjusted.get('projected_pf') is not None:
        adjusted['projected_pf'] = _round((adjusted.get('projected_pf') or 0.0) + offense_delta + margin_delta * 0.35)
    if adjusted.get('projected_pa') is not None:
        adjusted['projected_pa'] = _round((adjusted.get('projected_pa') or 0.0) - defense_delta - margin_delta * 0.2)
    if adjusted.get('projected_margin') is not None:
        adjusted['projected_margin'] = _round((adjusted.get('projected_margin') or 0.0) + offense_delta + defense_delta + margin_delta)

    confidence = dict(adjusted.get('confidence') or {})
    if confidence.get('score') is not None:
        confidence['score'] = round(max(0.32, float(confidence['score']) - float(profile.get('confidence_penalty') or 0.0)), 2)
        confidence['label'] = 'low' if confidence['score'] < 0.52 else ('medium' if confidence['score'] < 0.68 else 'high')
    adjusted['confidence'] = confidence
    adjusted['news_adjustment'] = 'availability_trade_layer'
    return adjusted


def _prediction_answer_with_news(route: Dict[str, Any], sport: str, items: List[Dict[str, Any]], related_news: List[Dict[str, Any]]) -> Dict[str, Any]:
    base = _answer_predictive(route, sport, items)
    prediction = base.get('prediction')
    if route.get('teams') and isinstance(prediction, dict):
        prediction = _apply_news_to_prediction(prediction, related_news)
        team_label = prediction.get('team_label') or (items[0].get('label') if items else 'This team')
        stat_word = POINTS_LABEL.get(sport, 'points')
        news_note = ''
        if related_news:
            tags = []
            if any('injury watch' in (n.get('impact_tags') or []) for n in related_news):
                tags.append('injury news')
            if any('roster move' in (n.get('impact_tags') or []) for n in related_news):
                tags.append('roster movement')
            if tags:
                news_note = f" Recent news adds some caution here, especially around {' and '.join(tags)}."
        answer = (
            f"My trend-based read is that {team_label} should be around {prediction.get('projected_pf')} {stat_word} scored, "
            f"{prediction.get('projected_pa')} allowed, and roughly {prediction.get('projected_margin')} in projected margin."
            f" Confidence is {(prediction.get('confidence') or {}).get('label', 'medium')} "
            f"({(prediction.get('confidence') or {}).get('score', '—')}).{news_note} {PREDICTION_DISCLAIMER}"
        )
        return {'answer': answer, 'prediction': prediction}
    if related_news and isinstance(prediction, dict) and prediction.get('ranked'):
        answer = base['answer'] + ' I also checked recent headlines so any active injury or roster noise can temper those rankings.'
        return {'answer': answer, 'prediction': prediction}
    return base
def answer_query(
    db: Session,
    *,
    sport: str,
    season: int,
    season_type: str,
    question: str,
    team_code: Optional[str] = None,
    session_id: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    sport = normalize_sport(sport)
    base_season = int(season)
    base_season_type = normalize_season_type(season_type)
    team_code = (team_code or "").upper().strip() or None
    question = (question or "").strip()
    conversation_history = [
        {"role": str(item.get("role") or "").strip().lower(), "text": str(item.get("text") or "").strip()}
        for item in (conversation_history or [])[-8:]
        if str(item.get("role") or "").strip().lower() in {"user", "assistant"} and str(item.get("text") or "").strip()
    ]

    if not question:
        return {
            "assistant_name": "Pulse",
            "answer": "Ask a question about recent trends, team comparisons, rankings, or forward-looking projections.",
            "supporting_items": [],
            "storylines": [],
            "route": None,
            "generated_plot": None,
            "prediction": None,
            "related_news": [],
        }

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
    history_key = _stable_hash(json.dumps(conversation_history, sort_keys=True, default=str)) if conversation_history else "nohist"
    session_key = (session_id or "nosession").strip() or "nosession"
    cache_key = f"ai:query:v9:{sport}:{resolved_season}:{resolved_season_type}:{team_code or 'all'}:{session_key}:{history_key}:{question_key}"
    cached = _cache_get(cache_key)
    if cached:
        try:
            return json.loads(cached)
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
        return {
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
            "generated_plot": None,
            "prediction": None,
            "related_news": [],
        }

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

    context = _build_query_context(summaries, route=route)
    items = context.get("items") or []
    should_fetch_news = bool(route.get("wants_news") or route.get("wants_prediction") or route.get("query_type") in {"news_summary", "news_impact", "predictive"})
    related_news = _fetch_related_news(db, sport=sport, route=route, team_code=team_code, limit=5) if should_fetch_news else []

    if route["query_type"] in {"smalltalk", "unknown"}:
        result = {
            "assistant_name": "Pulse",
            "answer": generate_smalltalk_response(question, conversation_history=conversation_history),
            "supporting_items": [],
            "storylines": [],
            "route": route,
            "generated_plot": None,
            "prediction": None,
            "related_news": [],
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
            "generated_plot": None,
            "prediction": None,
            "related_news": [],
        }
        _cache_set(cache_key, json.dumps(result), QUERY_TTL_SECONDS)
        return result

    if route["query_type"] in {"team_trend", "stat_explain", "predictive"} and route.get("teams"):
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

    if route["query_type"] == "predictive" and not route.get("teams"):
        # For league-wide predictions, rank all summaries by projected margin or offense threshold.
        items = _sort_rows(summaries, route.get("metric_focus") or "offense", "up")[:5]
        context["items"] = items

    storylines = build_storylines(
        db,
        sport=sport,
        season=resolved_season,
        season_type=resolved_season_type,
        team_code=team_code,
        limit=4,
    )

    prediction_payload = None
    if route["query_type"] == "predictive":
        pred = _prediction_answer_with_news(route, sport, items, related_news)
        answer = pred["answer"]
        prediction_payload = pred.get("prediction")
    elif route["query_type"] == "news_summary":
        answer = _build_news_summary_answer(route, items, related_news)
        answer = rewrite_grounded_pulse_answer(
            question=question,
            sport=sport,
            season=resolved_season,
            season_type=resolved_season_type,
            route=route,
            items=items,
            deterministic_answer=answer,
            conversation_history=conversation_history,
            session_id=session_id,
        )
    elif route["query_type"] == "news_impact":
        answer = _build_news_impact_answer(route, items, related_news, sport)
        answer = rewrite_grounded_pulse_answer(
            question=question,
            sport=sport,
            season=resolved_season,
            season_type=resolved_season_type,
            route=route,
            items=items,
            deterministic_answer=answer,
            conversation_history=conversation_history,
            session_id=session_id,
        )
    else:
        answer = answer_for_route(route, context, sport)
        if not answer:
            answer = _fallback_answer(context, route)
        answer = rewrite_grounded_pulse_answer(
            question=question,
            sport=sport,
            season=resolved_season,
            season_type=resolved_season_type,
            route=route,
            items=items,
            deterministic_answer=answer,
            conversation_history=conversation_history,
            session_id=session_id,
        )

    generated_plot = _build_generated_plot(
        route=route,
        sport=sport,
        season=resolved_season,
        season_type=resolved_season_type,
        items=items,
    )

    result = {
        "assistant_name": "Pulse",
        "answer": answer,
        "supporting_items": items[:5],
        "storylines": storylines,
        "route": route,
        "session_id": session_id,
        "memory_used": bool(conversation_history),
        "generated_plot": generated_plot,
        "prediction": prediction_payload,
        "prediction_disclaimer": PREDICTION_DISCLAIMER if route["query_type"] == "predictive" else None,
        "related_news": related_news[:5],
    }
    _cache_set(cache_key, json.dumps(result), QUERY_TTL_SECONDS)
    return result
