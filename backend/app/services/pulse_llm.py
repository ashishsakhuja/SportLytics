from __future__ import annotations

import json
from typing import Any, Dict, List

from app.services.pulse_providers import get_pulse_provider

PULSE_SYSTEM_PROMPT = """
You are Pulse, the SportLytics sports analytics assistant.

Your job is to explain sports data clearly, confidently, and naturally.

Style:
- Answer like a sharp sports analyst having an ongoing conversation.
- Vary the structure naturally instead of using the same template every time.
- Use bullets only when they genuinely improve clarity.
- Keep answers concise, easy to scan, and grounded in the data.
- When prior turns are provided, treat them as the current session context and continue naturally.

Rules:
- Use only the structured sports context provided.
- Do not invent teams, scores, injuries, schedules, rumors, rankings, or statistics.
- If the context is weak or missing, reply exactly: Not enough data yet.
- If the question is non-sports, politely say you can only analyze sports information.
- Respect the requested season and season type shown in the context.
- If the user is following up, connect briefly to the previous turn when useful.
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


def _compact_history(conversation_history: List[Dict[str, str]] | None, limit: int = 8) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for item in (conversation_history or [])[-limit:]:
        role = str(item.get("role") or "").strip().lower()
        text = str(item.get("text") or "").strip()
        if role not in {"user", "assistant"} or not text:
            continue
        out.append({"role": role, "text": text[:1200]})
    return out


def generate_smalltalk_response(question: str, conversation_history: List[Dict[str, str]] | None = None) -> str:
    prompt = (question or "").strip()
    if not prompt:
        return "I’m Pulse, the SportLytics assistant. Ask me about team trends, offense, defense, or league rankings."
    try:
        provider = get_pulse_provider()
        history = _compact_history(conversation_history, limit=6)
        user_prompt = prompt if not history else f"""Recent session context:
{_safe_json(history)}

Latest user message:
{prompt}"""
        text = provider.generate(
            system_prompt=SMALLTALK_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=110,
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
    conversation_history: List[Dict[str, str]] | None = None,
    session_id: str | None = None,
    related_news: List[Dict[str, Any]] | None = None,
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

    recent_history = _compact_history(conversation_history)

    compact_news = []
    for n in (related_news or [])[:5]:
        compact_news.append({
            "title": n.get("title"),
            "source": n.get("source"),
            "impact_tags": n.get("impact_tags"),
            "impact_direction": n.get("impact_direction"),
            "impact_summary": n.get("impact_summary"),
            "side_of_ball": n.get("side_of_ball"),
            "move_type": n.get("move_type"),
        })

    user_prompt = f"""
Session:
- session_id: {session_id or 'none'}

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

Recent conversation history:
{_safe_json(recent_history)}

Related news headlines for grounding:
{_safe_json(compact_news)}

Deterministic draft answer:
{deterministic_answer}

Rewrite the deterministic draft answer so it sounds premium, conversational, and naturally aware of the current session.
Requirements:
- Give a direct answer first.
- If this is a follow-up, briefly connect it to the previous turn when helpful.
- Use bullets only when they improve clarity.
- Keep the answer grounded and concise.
- Do not add facts beyond the route metadata, supporting items, conversation history, related news headlines, and deterministic draft answer.
- Never introduce a player, coach, or team name unless it already appears verbatim in the deterministic draft answer or the related news headlines above.
- If the exact person involved is unclear, say "the recent trade", "the recent injury update", or "the recent roster move" instead of guessing a name.
- Prefer summarizing the effect of the news instead of restating speculative details.
""".strip()

    try:
        provider = get_pulse_provider()
        text = provider.generate(
            system_prompt=PULSE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.42,
            max_tokens=260,
        )
        cleaned = (text or "").strip()
        return cleaned or deterministic_answer
    except Exception:
        return deterministic_answer
