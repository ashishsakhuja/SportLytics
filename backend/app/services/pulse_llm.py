from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Tuple

from app.services.pulse_providers import get_fallback_pulse_provider, get_pulse_provider

PULSE_SYSTEM_PROMPT = """
You are Pulse, the SportLytics sports analytics assistant.

Your job is to explain sports data clearly, confidently, and naturally.

Style:
- Sound like a sharp sports analyst, not a robot.
- Give a direct answer first, then support it with 1 to 3 concise points only if they add value.
- Vary the structure naturally: a short paragraph, or a short paragraph plus a few bullets.
- Weave confidence in naturally near the end instead of forcing a rigid template.
- Keep answers concise, premium, and easy to scan.

Rules:
- Use only the structured sports context provided.
- Do not invent teams, scores, injuries, schedules, rumors, rankings, or statistics.
- Preserve the facts from the deterministic answer.
- If the context is weak or missing, reply exactly: Not enough data yet.
- If the question is non-sports, politely say you can only analyze sports information.
- Respect the requested season and season type shown in the context.
- Never exceed 170 words.
- Avoid repeating the same response template every time.
- Do not use the labels Bottom line, Why, or Confidence unless the user explicitly asks for them.
""".strip()

MAX_TOKENS = int(os.getenv("PULSE_MAX_TOKENS", "320"))
TEMPERATURE = float(os.getenv("PULSE_TEMPERATURE", "0.35"))


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
        "Answer naturally instead of using a fixed template. A short paragraph is usually best; add 1-3 bullets only when they help. "
        "Mention confidence naturally near the end using the confidence payload, but do not use a rigid heading for it. "
        "Do not mention internal routing, cache details, or raw payload field names."
    )


def generate_smalltalk_response(question: str) -> str:
    q = (question or "").strip().lower()
    if any(x in q for x in ["hello", "hi", "hey", "yo", "what's up", "whats up"]):
        return "Hello — I’m Pulse, your SportLytics signal assistant. Ask about recent movers, team comparisons, offense, defense, or home-away splits."
    return "Sorry, I can only analyze sports information."


def _confidence_tail(extra_context: Dict[str, Any] | None) -> str:
    confidence = ((extra_context or {}).get("confidence") or {}) if isinstance(extra_context, dict) else {}
    label = str(confidence.get("label") or "").strip().lower()
    summary = str(confidence.get("summary") or "").strip()
    if label == "high":
        return summary or "I'm fairly confident in that read given the quality of the available stats."
    if label == "medium":
        return summary or "I'd treat that as a solid directional read, though some of the context is mixed."
    if label == "low":
        return summary or "I'd treat that as directional only because the supporting context is limited."
    return summary


def _naturalize_rigid_response(text: str, extra_context: Dict[str, Any] | None = None) -> str:
    raw = (text or "").strip()
    if not raw:
        return raw

    compact = raw.replace("\r\n", "\n")
    if "**Bottom line:**" not in compact and "**Why:**" not in compact and "**Confidence:**" not in compact:
        return compact

    bottom = ""
    why_block = ""
    conf = ""

    m_bottom = re.search(r"\*\*Bottom line:\*\*\s*(.*?)(?=\n\s*\*\*Why:\*\*|\n\s*\*\*Confidence:\*\*|$)", compact, re.S)
    if m_bottom:
        bottom = m_bottom.group(1).strip()

    m_why = re.search(r"\*\*Why:\*\*\s*(.*?)(?=\n\s*\*\*Confidence:\*\*|$)", compact, re.S)
    if m_why:
        why_block = m_why.group(1).strip()

    m_conf = re.search(r"\*\*Confidence:\*\*\s*(.*)$", compact, re.S)
    if m_conf:
        conf = m_conf.group(1).strip()

    parts: List[str] = []
    if bottom:
        parts.append(bottom)

    if why_block:
        bullets: List[str] = []
        for line in why_block.splitlines():
            item = re.sub(r"^[\-•]\s*", "", line.strip())
            if item:
                bullets.append(f"- {item}")
        if bullets:
            parts.append("\n".join(bullets[:3]))
        elif why_block:
            parts.append(why_block)

    tail = _confidence_tail(extra_context)
    if conf and not tail:
        tail = conf
    if tail:
        tail = tail.rstrip(".") + "."
        if not re.match(r"(?i)^(i'm|i am|this is|that is|it's|its|treat|confidence)", tail):
            tail = f"I'm fairly confident in that read because {tail[0].lower() + tail[1:]}"
        parts.append(tail)

    return "\n\n".join(part for part in parts if part).strip() or compact


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
            rewritten = _naturalize_rigid_response(rewritten, extra_context)
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
                rewritten = _naturalize_rigid_response(rewritten, extra_context)
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
