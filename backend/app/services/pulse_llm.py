from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

from app.services.pulse_providers import get_fallback_pulse_provider, get_pulse_provider

PULSE_SYSTEM_PROMPT = """
You are Pulse, the SportLytics sports analytics assistant.

Your job is to explain sports data clearly, confidently, and naturally.

Style:
- Start with a direct answer to the user's question.
- Then support it with 2 to 4 short bullet-style insights when data is available.
- Sound like a sports analyst, not a robot.
- Keep answers concise and easy to scan.
- Prefer crisp comparisons and trend language over generic filler.

Rules:
- Use only the structured sports context provided.
- Do not invent teams, scores, injuries, schedules, rumors, rankings, or statistics.
- If the context is weak or missing, reply exactly: Not enough data yet.
- If the question is non-sports, politely say you can only analyze sports information.
- Respect the requested season and season type shown in the context.
- Never exceed 150 words.
""".strip()

MAX_TOKENS = int(os.getenv("PULSE_MAX_TOKENS", "320"))
TEMPERATURE = float(os.getenv("PULSE_TEMPERATURE", "0.35"))


def _serialize_items(items: List[Dict[str, Any]]) -> str:
    trimmed: List[Dict[str, Any]] = []
    for row in items[:6]:
        trimmed.append({
            "team_code": row.get("team_code"),
            "label": row.get("label"),
            "recent_record": row.get("recent_record"),
            "last5_avg_margin": row.get("last5_avg_margin"),
            "prev5_avg_margin": row.get("prev5_avg_margin"),
            "margin_delta": row.get("margin_delta"),
            "last5_avg_pf": row.get("last5_avg_pf"),
            "prev5_avg_pf": row.get("prev5_avg_pf"),
            "offense_delta": row.get("offense_delta"),
            "last5_avg_pa": row.get("last5_avg_pa"),
            "prev5_avg_pa": row.get("prev5_avg_pa"),
            "defense_delta": row.get("defense_delta"),
            "turnover_delta": row.get("turnover_delta"),
            "home_away_gap": row.get("home_away_gap"),
            "recent_sos": row.get("recent_sos"),
            "season_sos": row.get("season_sos"),
        })
    return json.dumps(trimmed, indent=2, default=str)


def _build_user_prompt(
    *,
    question: str,
    sport: str,
    season: int,
    season_type: str,
    route: Dict[str, Any],
    items: List[Dict[str, Any]],
    deterministic_answer: str,
    extra_context: Dict[str, Any] | None = None,
) -> str:
    payload = {
        "question": question,
        "sport": sport,
        "season": season,
        "season_type": season_type,
        "route": route,
        "deterministic_answer": deterministic_answer,
        "supporting_items": items[:6],
        "extra_context": extra_context or {},
    }
    return (
        "User question:\n"
        f"{question}\n\n"
        "Pulse context:\n"
        f"{json.dumps(payload, indent=2, default=str)}\n\n"
        "Rewrite the deterministic answer into a premium sports-analytics response. "
        "Keep it tight, preserve the same facts, and do not add any new information. "
        "Use a direct lead sentence followed by compact bullets only when they help readability."
    )


def generate_smalltalk_response(question: str) -> str:
    q = (question or "").strip().lower()
    if any(x in q for x in ["hello", "hi", "hey", "yo", "what's up", "whats up"]):
        return "Hello — I’m Pulse, your SportLytics signal assistant. Ask about recent movers, team comparisons, offense, defense, or home-away splits."
    return "Sorry, I can only analyze sports information."


def _provider_name(provider: Any) -> str:
    return provider.__class__.__name__


def rewrite_grounded_pulse_answer(
    *,
    question: str,
    sport: str,
    season: int,
    season_type: str,
    route: Dict[str, Any],
    items: List[Dict[str, Any]],
    deterministic_answer: str,
    extra_context: Dict[str, Any] | None = None,
) -> str:
    text, _ = rewrite_grounded_pulse_answer_with_meta(
        question=question,
        sport=sport,
        season=season,
        season_type=season_type,
        route=route,
        items=items,
        deterministic_answer=deterministic_answer,
        extra_context=extra_context,
    )
    return text


def rewrite_grounded_pulse_answer_with_meta(
    *,
    question: str,
    sport: str,
    season: int,
    season_type: str,
    route: Dict[str, Any],
    items: List[Dict[str, Any]],
    deterministic_answer: str,
    extra_context: Dict[str, Any] | None = None,
) -> Tuple[str, Dict[str, Any]]:
    answer = (deterministic_answer or "").strip() or "Not enough data yet."
    if answer == "Not enough data yet.":
        return answer, {
            "provider": "none",
            "fallback_used": False,
            "rewrite_applied": False,
            "source": "deterministic",
            "note": "empty-deterministic-answer",
        }

    user_prompt = _build_user_prompt(
        question=question,
        sport=sport,
        season=season,
        season_type=season_type,
        route=route,
        items=items,
        deterministic_answer=answer,
        extra_context=extra_context,
    )

    primary = None
    fallback = None
    try:
        primary = get_pulse_provider()
    except Exception as exc:
        return answer, {
            "provider": "none",
            "fallback_used": False,
            "rewrite_applied": False,
            "source": "deterministic",
            "note": f"primary-provider-unavailable:{exc}",
        }

    try:
        rewritten = (primary.generate(
            system_prompt=PULSE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        ) or "").strip()
        if rewritten:
            return rewritten, {
                "provider": _provider_name(primary),
                "fallback_used": False,
                "rewrite_applied": True,
                "source": "llm",
            }
    except Exception as exc:
        primary_error = exc
    else:
        primary_error = RuntimeError("empty-primary-response")

    try:
        fallback = get_fallback_pulse_provider()
    except Exception:
        fallback = None

    if fallback is not None and _provider_name(fallback) != _provider_name(primary):
        try:
            rewritten = (fallback.generate(
                system_prompt=PULSE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            ) or "").strip()
            if rewritten:
                return rewritten, {
                    "provider": _provider_name(fallback),
                    "fallback_used": True,
                    "rewrite_applied": True,
                    "source": "llm",
                    "note": f"primary-failed:{primary_error}",
                }
        except Exception as fallback_exc:
            return answer, {
                "provider": "none",
                "fallback_used": True,
                "rewrite_applied": False,
                "source": "deterministic",
                "note": f"primary-failed:{primary_error};fallback-failed:{fallback_exc}",
            }

    return answer, {
        "provider": "none",
        "fallback_used": False,
        "rewrite_applied": False,
        "source": "deterministic",
        "note": f"primary-failed:{primary_error}",
    }
