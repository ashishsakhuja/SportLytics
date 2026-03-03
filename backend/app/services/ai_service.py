import os
import json
import hashlib
from typing import Any, Dict

from openai import OpenAI

from app.services.redis_cache import get_redis

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CAPTION_TTL_SECONDS = int(os.getenv("AI_CAPTION_TTL_SECONDS", "3600"))

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

  resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
      {"role": "system", "content": SYSTEM_PROMPT},
      {"role": "user", "content": user_prompt},
    ],
    temperature=0.2,
    max_tokens=120,
  )

  return (resp.choices[0].message.content or "").strip() or "Not enough data yet."


def _stable_summary_hash(summary: Dict[str, Any]) -> str:
  dumped = json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
  return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def _caption_cache_key(
  *,
  chart_id: str,
  sport: str,
  season: int,
  season_type: str,
  team: str,
  summary: Dict[str, Any],
) -> str:
  s_hash = _stable_summary_hash(summary)
  return f"ai:caption:{chart_id}:{sport}:{season}:{season_type}:{team}:{s_hash}"


def generate_chart_caption_cached(
  *,
  chart_id: str,
  sport: str,
  season: int,
  season_type: str,
  team: str,
  summary: Dict[str, Any],
) -> str:
  # Always safe fallback
  if not summary or len(summary) == 0:
    return "Not enough data yet."

  key = _caption_cache_key(
    chart_id=chart_id,
    sport=sport,
    season=season,
    season_type=season_type,
    team=team,
    summary=summary,
  )

  r = get_redis()
  if r is not None:
    try:
      # quick health check to avoid stack traces on every request
      r.ping()
      cached = r.get(key)
      if cached:
        return cached
    except Exception:
      # Redis down/unreachable -> fail open
      r = None

  caption = generate_chart_caption(chart_id=chart_id, summary=summary)

  if r is not None:
    try:
      ttl = CAPTION_TTL_SECONDS if caption != "Not enough data yet." else min(300, CAPTION_TTL_SECONDS)
      r.setex(key, ttl, caption)
    except Exception:
      # Cache write failed -> ignore, return caption
      pass

  return caption