from __future__ import annotations

import json
from typing import Any, Dict, List

from app.services.pulse_providers import get_pulse_provider

PULSE_SYSTEM_PROMPT = """
You are Pulse, the SportLytics sports analytics assistant.

Your job is to explain sports data clearly, confidently, and naturally.

Style:
- Start with a direct answer to the user's question.
- Then support it with 2 to 3 short bullet-style insights when data is available.
- Sound like a sports analyst, not a robot.
- Keep answers concise and easy to scan.

Rules:
- Use only the structured sports context provided.
- Do not invent teams, scores, injuries, schedules, rumors, rankings, or statistics.
- If the context is weak or missing, reply exactly: Not enough data yet.
- If the question is non-sports, politely say you can only analyze sports information.
- Respect the requested season and season type shown in the context.
""".strip()

SMALLTALK_SYSTEM_PROMPT = """
You are Pulse, the SportLytics assistant.

You specialize in sports analytics. For greetings or casual small talk, respond naturally and briefly.
For non-sports or out-of-scope questions, politely say that you mainly focus on sports analytics
and invite the user to ask about teams, trends, rankings, offense, or defense.

Keep the tone warm, human, and concise.
Keep answers under 2 sentences.
Do not invent sports stats.
""".strip()


def _safe_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def generate_smalltalk_response(question: str) -> str:
    prompt = (question or "").strip()
    if not prompt:
        return "I’m Pulse, the SportLytics assistant. Ask me about team trends, offense, defense, or league rankings."
    try:
        provider = get_pulse_provider()
        text = provider.generate(
            system_prompt=SMALLTALK_SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=0.7,
            max_tokens=80,
        )
        if text.strip():
            return text.strip()
    except Exception:
        pass
    return "I’m Pulse, the SportLytics assistant. Ask me about team trends, offense, defense, or league rankings."


def rewrite_grounded_pulse_answer(
    *,
    question: str,
    sport: str,
    season: int,
    season_type: str,
    route: Dict[str, Any],
    items: List[Dict[str, Any]],
    deterministic_answer: str,
) -> str:
    if not deterministic_answer or deterministic_answer.strip() == "Not enough data yet.":
        return "Not enough data yet."

    compact_items = []
    for row in items[:5]:
        compact_items.append(
            {
                "team_code": row.get("team_code"),
                "label": row.get("label"),
                "recent_record": row.get("recent_record"),
                "season_avg_margin": row.get("season_avg_margin"),
                "margin_delta": row.get("margin_delta"),
                "offense_delta": row.get("offense_delta"),
                "defense_delta": row.get("defense_delta"),
                "last5_avg_margin": row.get("last5_avg_margin"),
                "prev5_avg_margin": row.get("prev5_avg_margin"),
                "last5_avg_pf": row.get("last5_avg_pf"),
                "prev5_avg_pf": row.get("prev5_avg_pf"),
                "last5_avg_pa": row.get("last5_avg_pa"),
                "prev5_avg_pa": row.get("prev5_avg_pa"),
                "turnover_delta": row.get("turnover_delta"),
                "home_away_gap": row.get("home_away_gap"),
                "recent_sos": row.get("recent_sos"),
            }
        )

    user_prompt = f"""
Question:
{question}

Sport context:
- sport: {sport}
- season: {season}
- season_type: {season_type}

Route metadata:
{_safe_json(route)}

Supporting items:
{_safe_json(compact_items)}

Deterministic draft answer:
{deterministic_answer}

Rewrite the deterministic draft answer so it sounds premium and easy to scan.
Requirements:
- Give a direct answer first.
- Then add 2 or 3 short bullet-style insights using hyphen bullets when useful.
- Stay fully grounded in the supplied data.
- Respect the requested season and team context.
- Do not add any facts beyond the route metadata, supporting items, and deterministic draft answer.
""".strip()

    try:
        provider = get_pulse_provider()
        text = provider.generate(
            system_prompt=PULSE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.35,
            max_tokens=220,
        )
        cleaned = (text or "").strip()
        return cleaned or deterministic_answer
    except Exception:
        return deterministic_answer
