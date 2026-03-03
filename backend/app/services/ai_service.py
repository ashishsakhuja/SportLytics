import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are a sports analytics assistant.

Rules:
- Use ONLY the numbers provided.
- Do NOT invent statistics.
- If insufficient data, respond exactly with:
  "Not enough data yet."
- Keep response 1-2 sentences maximum.
- No hype. No emojis. No assumptions.
- Be objective and analytical.
- Do NOT take credit for any produced results
- Do NOT use any foul language or inappropriate content.
"""

def generate_chart_caption(chart_id: str, summary: dict) -> str:
    if not summary or len(summary) == 0:
        return "Not enough data yet."

    user_prompt = f"""
Chart ID: {chart_id}

Data Summary:
{summary}

Generate a concise analytical insight.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # fast + cheap
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=120,
    )

    return response.choices[0].message.content.strip()