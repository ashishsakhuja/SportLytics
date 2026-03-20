from __future__ import annotations

import json
from typing import Any, Dict, List

from app.services.pulse_providers import get_pulse_provider

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
- Never exceed 160 words.
""".strip()


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
            "recent_sos": row.get("recent_sos"),
            "season_sos": row.get("season_sos"),
        })
    return json.dumps(trimmed, ensure_ascii=False, indent=2, sort_keys=True)


def _serialize_context(extra_context: Dict[str, Any] | None) -> str:
    if not extra_context:
        return "{}"
    return json.dumps(extra_context, ensure_ascii=False, indent=2, sort_keys=True, default=str)


def generate_smalltalk_response(question: str) -> str:
    provider = get_pulse_provider()
    prompt = f"""
User message: {question}

Respond as Pulse in 1 to 2 short sentences.
- Be friendly and confident.
- If the message is unrelated to sports analytics, say you can analyze sports trends, comparisons, rankings, and chart context.
- No emojis.
""".strip()
    try:
        return provider.generate_sync(system_prompt=PULSE_SYSTEM_PROMPT, user_prompt=prompt)
    except Exception:
        q = (question or "").lower()
        if any(t in q for t in ["hi", "hello", "hey"]):
            return "Hello — I’m Pulse, your SportLytics signal assistant. Ask me about trends, comparisons, rankings, or what stands out in a chart."
        return "I can help with sports analytics questions, team trends, comparisons, rankings, and chart explanations."


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
    provider = get_pulse_provider()
    user_prompt = f"""
User question:
{question}

Sport context:
- sport: {sport}
- season: {season}
- season_type: {season_type}
- query_type: {route.get('query_type')}
- metric_focus: {route.get('metric_focus')}
- direction: {route.get('direction')}
- teams: {route.get('teams')}
- seasons: {route.get('seasons')}

Structured team summaries:
{_serialize_items(items)}

Additional contextual payload:
{_serialize_context(extra_context)}

Deterministic draft answer:
{deterministic_answer}

Rewrite the deterministic answer into a polished Pulse response.
Return:
- 1 direct conclusion sentence
- 2 to 4 concise bullet-style insights if the data supports them
- at most 1 short closing sentence
Do not add any facts beyond the structured context above.
""".strip()
    try:
        text = provider.generate_sync(system_prompt=PULSE_SYSTEM_PROMPT, user_prompt=user_prompt)
        return (text or "").strip() or deterministic_answer
    except Exception:
        return deterministic_answer
