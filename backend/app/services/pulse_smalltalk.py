from __future__ import annotations

import os

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are Pulse, the SportLytics assistant.

You specialize in sports analytics, especially team trends, comparisons, offense, defense, rankings,
recent form, and home-away splits.

For greetings or casual small talk, respond naturally and briefly.
For non-sports or out-of-scope questions, politely say that you mainly focus on sports analytics
and invite the user to ask about teams, trends, or rankings.

Keep the tone warm, human, and concise.
Keep answers under 2 sentences.
Do not invent sports stats in small-talk replies.
""".strip()


def generate_smalltalk_response(question: str) -> str:
    prompt = (question or "").strip()
    if not prompt:
        return "I’m Pulse, the SportLytics assistant. Ask me about team trends, offense, defense, or league rankings."

    try:
        resp = client.chat.completions.create(
            model=os.getenv("PULSE_SMALLTALK_MODEL", "gpt-4o-mini"),
            temperature=0.7,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        content = resp.choices[0].message.content
        if content and content.strip():
            return content.strip()
    except Exception:
        pass

    return "I’m Pulse, the SportLytics assistant. Ask me about team trends, offense, defense, or league rankings."
