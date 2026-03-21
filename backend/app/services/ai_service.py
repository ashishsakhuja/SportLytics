import os
import json
import hashlib
from typing import Any, Dict

from openai import OpenAI

from app.services.redis_cache import get_redis

CAPTION_TTL_SECONDS = int(os.getenv("AI_CAPTION_TTL_SECONDS", "3600"))
CHART_QUERY_TTL_SECONDS = int(os.getenv("AI_CHART_QUERY_TTL_SECONDS", "1800"))

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

_client: OpenAI | None = None


def _get_openai_client() -> OpenAI | None:
  global _client

  if _client is not None:
    return _client

  api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
  if not api_key:
    return None

  try:
    _client = OpenAI(api_key=api_key)
  except Exception:
    return None

  return _client


def generate_chart_caption(chart_id: str, summary: dict) -> str:
  if not summary or len(summary) == 0:
    return "Not enough data yet."

  client = _get_openai_client()
  if client is None:
    return "Not enough data yet."

  user_prompt = f"""
Chart ID: {chart_id}

Data Summary:
{summary}

Generate a concise analytical insight.
"""

  try:
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
  except Exception:
    return "Not enough data yet."


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
      r.ping()
      cached = r.get(key)
      if cached:
        return cached
    except Exception:
      r = None

  caption = generate_chart_caption(chart_id=chart_id, summary=summary)

  if r is not None:
    try:
      ttl = CAPTION_TTL_SECONDS if caption != "Not enough data yet." else min(300, CAPTION_TTL_SECONDS)
      r.setex(key, ttl, caption)
    except Exception:
      pass

  return caption


def generate_chart_answer(
  *,
  chart_id: str,
  chart_title: str,
  sport: str,
  season: int,
  season_type: str,
  team: str | None,
  summary: dict,
  question: str,
) -> str:
  if not summary or len(summary) == 0 or not (question or "").strip():
    return "Not enough data yet."

  client = _get_openai_client()
  if client is None:
    return "Not enough data yet."

  user_prompt = f"""
Chart ID: {chart_id}
Chart Title: {chart_title}
Sport: {sport}
Season: {season}
Season Type: {season_type}
Team: {team or 'N/A'}

Question:
{question}

Data Summary:
{summary}

Answer the question using only this chart summary.
"""

  try:
    resp = client.chat.completions.create(
      model="gpt-4o-mini",
      messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
      ],
      temperature=0.2,
      max_tokens=180,
    )
    return (resp.choices[0].message.content or "").strip() or "Not enough data yet."
  except Exception:
    return "Not enough data yet."


def generate_chart_answer_cached(
  *,
  chart_id: str,
  chart_title: str,
  sport: str,
  season: int,
  season_type: str,
  team: str | None,
  summary: Dict[str, Any],
  question: str,
) -> str:
  if not summary or len(summary) == 0 or not (question or "").strip():
    return "Not enough data yet."

  key = (
    f"ai:chart-query:{chart_id}:{sport}:{season}:{season_type}:{team or 'all'}:"
    f"{_stable_summary_hash(summary)}:{hashlib.sha256(question.strip().lower().encode('utf-8')).hexdigest()}"
  )

  r = get_redis()
  if r is not None:
    try:
      r.ping()
      cached = r.get(key)
      if cached:
        return cached
    except Exception:
      r = None

  answer = generate_chart_answer(
    chart_id=chart_id,
    chart_title=chart_title,
    sport=sport,
    season=season,
    season_type=season_type,
    team=team,
    summary=summary,
    question=question,
  )

  if r is not None:
    try:
      ttl = CHART_QUERY_TTL_SECONDS if answer != "Not enough data yet." else min(300, CHART_QUERY_TTL_SECONDS)
      r.setex(key, ttl, answer)
    except Exception:
      pass

  return answer