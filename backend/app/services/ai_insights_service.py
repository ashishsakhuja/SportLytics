from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from openai import OpenAI
from sqlalchemy.orm import Session

from app.models import Game, Team
from app.services.redis_cache import get_redis
from app.services.team_aliases import TEAM_ALIASES

SUPPORTED_SPORTS = {"nfl", "nba", "mlb", "nhl"}
POINTS_LABEL = {"nfl": "points", "nba": "points", "mlb": "runs", "nhl": "goals"}
QUERY_TTL_SECONDS = int(os.getenv("AI_QUERY_TTL_SECONDS", "900"))
STORYLINES_TTL_SECONDS = int(os.getenv("AI_STORYLINES_TTL_SECONDS", "900"))
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@dataclass
class TeamInsightSummary:
    team_code: str
    label: str
    games: int
    wins: int
    losses: int
    season_avg_pf: Optional[float]
    season_avg_pa: Optional[float]
    season_avg_margin: Optional[float]
    last5_avg_pf: Optional[float]
    last5_avg_pa: Optional[float]
    last5_avg_margin: Optional[float]
    prev5_avg_pf: Optional[float]
    prev5_avg_pa: Optional[float]
    prev5_avg_margin: Optional[float]
    offense_delta: Optional[float]
    defense_delta: Optional[float]
    margin_delta: Optional[float]
    home_avg_margin: Optional[float]
    away_avg_margin: Optional[float]
    home_away_gap: Optional[float]
    recent_record: str
    recent_win_pct: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_code": self.team_code,
            "label": self.label,
            "games": self.games,
            "wins": self.wins,
            "losses": self.losses,
            "season_avg_pf": self.season_avg_pf,
            "season_avg_pa": self.season_avg_pa,
            "season_avg_margin": self.season_avg_margin,
            "last5_avg_pf": self.last5_avg_pf,
            "last5_avg_pa": self.last5_avg_pa,
            "last5_avg_margin": self.last5_avg_margin,
            "prev5_avg_pf": self.prev5_avg_pf,
            "prev5_avg_pa": self.prev5_avg_pa,
            "prev5_avg_margin": self.prev5_avg_margin,
            "offense_delta": self.offense_delta,
            "defense_delta": self.defense_delta,
            "margin_delta": self.margin_delta,
            "home_avg_margin": self.home_avg_margin,
            "away_avg_margin": self.away_avg_margin,
            "home_away_gap": self.home_away_gap,
            "recent_record": self.recent_record,
            "recent_win_pct": self.recent_win_pct,
        }


def _safe_avg(values: List[Optional[float]]) -> Optional[float]:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _round(v: Optional[float], digits: int = 2) -> Optional[float]:
    if v is None:
        return None
    return round(float(v), digits)


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


def _finalish_filter():
    return sa.and_(
        Game.home_score.isnot(None),
        Game.away_score.isnot(None),
        sa.or_(Game.status == "final", Game.status.is_(None)),
    )


def _norm_sport(sport: str) -> str:
    sport = (sport or "").lower().strip()
    if sport not in SUPPORTED_SPORTS:
        raise ValueError(f"Unsupported sport '{sport}'")
    return sport


def _team_label_map(db: Session, sport: str) -> Dict[str, str]:
    rows = db.query(Team).filter(Team.sport == sport).all()
    out: Dict[str, str] = {}
    for row in rows:
        label = f"{row.city} {row.name}".strip() if row.city else row.name
        out[row.team_code.upper()] = label
    return out


def _load_team_games(db: Session, sport: str, season: int, season_type: str, team_code: Optional[str] = None) -> List[Dict[str, Any]]:
    q = (
        db.query(Game)
        .filter(
            Game.sport == sport,
            Game.season == season,
            Game.season_type == season_type,
            Game.game_date.isnot(None),
            _finalish_filter(),
        )
        .order_by(Game.game_date.asc())
    )

    games = q.all()
    rows: List[Dict[str, Any]] = []
    for g in games:
        for side in ("home", "away"):
            is_home = side == "home"
            code = (g.home_team_code if is_home else g.away_team_code).upper()
            if team_code and code != team_code:
                continue
            pf = g.home_score if is_home else g.away_score
            pa = g.away_score if is_home else g.home_score
            if pf is None or pa is None:
                continue
            rows.append({
                "team_code": code,
                "date": g.game_date,
                "home_away": "home" if is_home else "away",
                "pf": int(pf),
                "pa": int(pa),
                "margin": int(pf) - int(pa),
                "result": "W" if pf > pa else ("L" if pf < pa else "T"),
                "opponent": (g.away_team_code if is_home else g.home_team_code).upper(),
            })
    return rows


def build_team_summaries(db: Session, *, sport: str, season: int, season_type: str, team_code: Optional[str] = None) -> List[Dict[str, Any]]:
    sport = _norm_sport(sport)
    season_type = (season_type or "REG").upper().strip()
    team_code = (team_code or "").upper().strip() or None
    label_map = _team_label_map(db, sport)
    games = _load_team_games(db, sport, season, season_type, team_code)

    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for row in games:
        buckets.setdefault(row["team_code"], []).append(row)

    summaries: List[TeamInsightSummary] = []
    for code, rows in buckets.items():
        rows = sorted(rows, key=lambda x: x["date"])
        last5 = rows[-5:]
        prev5 = rows[-10:-5]
        home_rows = [r for r in rows if r["home_away"] == "home"]
        away_rows = [r for r in rows if r["home_away"] == "away"]
        wins = sum(1 for r in rows if r["result"] == "W")
        losses = sum(1 for r in rows if r["result"] == "L")
        last5_w = sum(1 for r in last5 if r["result"] == "W")
        last5_l = sum(1 for r in last5 if r["result"] == "L")
        last5_t = sum(1 for r in last5 if r["result"] == "T")
        recent_games = len(last5)
        last5_pf = _safe_avg([r["pf"] for r in last5])
        last5_pa = _safe_avg([r["pa"] for r in last5])
        last5_margin = _safe_avg([r["margin"] for r in last5])
        prev5_pf = _safe_avg([r["pf"] for r in prev5])
        prev5_pa = _safe_avg([r["pa"] for r in prev5])
        prev5_margin = _safe_avg([r["margin"] for r in prev5])
        summaries.append(
            TeamInsightSummary(
                team_code=code,
                label=label_map.get(code, code),
                games=len(rows),
                wins=wins,
                losses=losses,
                season_avg_pf=_round(_safe_avg([r["pf"] for r in rows])),
                season_avg_pa=_round(_safe_avg([r["pa"] for r in rows])),
                season_avg_margin=_round(_safe_avg([r["margin"] for r in rows])),
                last5_avg_pf=_round(last5_pf),
                last5_avg_pa=_round(last5_pa),
                last5_avg_margin=_round(last5_margin),
                prev5_avg_pf=_round(prev5_pf),
                prev5_avg_pa=_round(prev5_pa),
                prev5_avg_margin=_round(prev5_margin),
                offense_delta=_round((last5_pf - prev5_pf) if (last5_pf is not None and prev5_pf is not None) else None),
                defense_delta=_round((prev5_pa - last5_pa) if (last5_pa is not None and prev5_pa is not None) else None),
                margin_delta=_round((last5_margin - prev5_margin) if (last5_margin is not None and prev5_margin is not None) else None),
                home_avg_margin=_round(_safe_avg([r["margin"] for r in home_rows])),
                away_avg_margin=_round(_safe_avg([r["margin"] for r in away_rows])),
                home_away_gap=_round((_safe_avg([r["margin"] for r in home_rows]) - _safe_avg([r["margin"] for r in away_rows])) if home_rows and away_rows else None),
                recent_record=f"{last5_w}-{last5_l}" + (f"-{last5_t}" if last5_t else ""),
                recent_win_pct=_round((last5_w / recent_games) if recent_games else None),
            )
        )

    summaries.sort(key=lambda s: ((s.margin_delta if s.margin_delta is not None else -9999), (s.season_avg_margin if s.season_avg_margin is not None else -9999)), reverse=True)
    return [s.to_dict() for s in summaries]


def _storyline_prompt(item: Dict[str, Any], *, sport: str, season: int, season_type: str) -> str:
    points_label = POINTS_LABEL.get(sport, "points")
    return (
        "Write a concise sports analytics storyline in 2 sentences maximum.\n"
        "Rules:\n"
        "- Use only the provided numbers.\n"
        "- No speculation or future predictions.\n"
        "- Sound sharp and analytical, like a dashboard insight.\n"
        f"- Use '{points_label}' as the scoring term when relevant.\n\n"
        f"Sport: {sport.upper()}\nSeason: {season}\nSeason type: {season_type}\n"
        f"Insight payload: {json.dumps(item, sort_keys=True)}"
    )


def _generate_storyline_text(item: Dict[str, Any], *, sport: str, season: int, season_type: str) -> str:
    prompt = _storyline_prompt(item, sport=sport, season=season, season_type=season_type)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You turn structured sports trend summaries into brief grounded dashboard storylines.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=120,
    )
    return (resp.choices[0].message.content or "").strip() or "Not enough data yet."


def build_storylines(db: Session, *, sport: str, season: int, season_type: str, team_code: Optional[str] = None, limit: int = 6) -> List[Dict[str, Any]]:
    sport = _norm_sport(sport)
    season_type = (season_type or "REG").upper().strip()
    team_code = (team_code or "").upper().strip() or None

    cache_key = f"ai:storylines:{sport}:{season}:{season_type}:{team_code or 'all'}:{limit}"
    cached = _cache_get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass

    summaries = build_team_summaries(db, sport=sport, season=season, season_type=season_type, team_code=team_code)
    if not summaries:
        return []

    candidates: List[Dict[str, Any]] = []
    valid_offense = [s for s in summaries if s.get("offense_delta") is not None]
    valid_defense = [s for s in summaries if s.get("defense_delta") is not None]
    valid_margin = [s for s in summaries if s.get("margin_delta") is not None]
    valid_split = [s for s in summaries if s.get("home_away_gap") is not None]

    def pick(sorted_rows: List[Dict[str, Any]], category: str, title: str, direction: str, value_key: str):
        if not sorted_rows:
            return
        row = sorted_rows[0]
        candidates.append({
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
                "last5_avg_pf": row.get("last5_avg_pf"),
                "last5_avg_pa": row.get("last5_avg_pa"),
                "prev5_avg_pf": row.get("prev5_avg_pf"),
                "prev5_avg_pa": row.get("prev5_avg_pa"),
                "home_avg_margin": row.get("home_avg_margin"),
                "away_avg_margin": row.get("away_avg_margin"),
                value_key: row.get(value_key),
            },
        })

    pick(sorted(valid_offense, key=lambda x: x["offense_delta"], reverse=True), "offense", "{team} offense gaining momentum", "up", "offense_delta")
    pick(sorted(valid_defense, key=lambda x: x["defense_delta"], reverse=True), "defense", "{team} tightening up defensively", "up", "defense_delta")
    pick(sorted(valid_margin, key=lambda x: x["margin_delta"], reverse=True), "margin", "{team} winning the recent form battle", "up", "margin_delta")
    pick(sorted(valid_margin, key=lambda x: x["margin_delta"]), "margin", "{team} sliding on recent margin", "down", "margin_delta")
    pick(sorted(valid_split, key=lambda x: abs(x["home_away_gap"]), reverse=True), "split", "{team} showing a strong location split", "split", "home_away_gap")

    seen: set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for item in candidates:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        deduped.append(item)

    out: List[Dict[str, Any]] = []
    for item in deduped[:limit]:
        try:
            item["caption"] = _generate_storyline_text(item, sport=sport, season=season, season_type=season_type)
        except Exception:
            support = item["support"]
            item["caption"] = (
                f"{item['team_label']} has a {item['category']} signal in the latest sample. "
                f"Recent record: {support.get('recent_record')}, last-5 margin: {support.get('last5_avg_margin')}"
            )
        out.append(item)

    _cache_set(cache_key, json.dumps(out), STORYLINES_TTL_SECONDS)
    return out


def _extract_team_codes(question: str, known_codes: set[str]) -> List[str]:
    q = (question or "").lower()
    found: List[str] = []
    for token in re.findall(r"[a-zA-Z]{2,}(?:\s+[a-zA-Z]{2,})?", q):
        raw = token.strip().lower()
        code = TEAM_ALIASES.get(raw)
        if code and code in known_codes and code not in found:
            found.append(code)
    for code in known_codes:
        if re.search(rf"{re.escape(code.lower())}", q) and code not in found:
            found.append(code)
    return found[:4]


def answer_query(db: Session, *, sport: str, season: int, season_type: str, question: str, team_code: Optional[str] = None) -> Dict[str, Any]:
    sport = _norm_sport(sport)
    season_type = (season_type or "REG").upper().strip()
    team_code = (team_code or "").upper().strip() or None
    question = (question or "").strip()
    if not question:
        return {"answer": "Ask a question about recent trends, team comparisons, or who is rising and falling.", "supporting_items": []}

    cache_key = f"ai:query:{sport}:{season}:{season_type}:{team_code or 'all'}:{hash(question.lower())}"
    cached = _cache_get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass

    summaries = build_team_summaries(db, sport=sport, season=season, season_type=season_type, team_code=team_code)
    if not summaries:
        return {"answer": "Not enough data yet.", "supporting_items": []}

    known_codes = {s["team_code"] for s in summaries}
    requested_codes = _extract_team_codes(question, known_codes)
    narrowed = [s for s in summaries if s["team_code"] in requested_codes] if requested_codes else summaries
    if len(narrowed) > 12:
        # keep the most relevant teams by strongest recent movement when the prompt is broad
        narrowed = sorted(
            narrowed,
            key=lambda s: abs(s.get("margin_delta") or 0) + abs(s.get("offense_delta") or 0) + abs(s.get("defense_delta") or 0),
            reverse=True,
        )[:12]

    storylines = build_storylines(db, sport=sport, season=season, season_type=season_type, team_code=team_code, limit=4)
    payload = {
        "sport": sport,
        "season": season,
        "season_type": season_type,
        "question": question,
        "team_filter": team_code,
        "teams": narrowed,
        "storylines": storylines,
        "scoring_term": POINTS_LABEL.get(sport, "points"),
    }

    user_prompt = (
        "Answer the user's sports analytics question using ONLY the structured context.\n"
        "Rules:\n"
        "- Do not invent stats or players.\n"
        "- Stay grounded in the supplied team summaries.\n"
        "- If comparing teams, mention the key numeric differences.\n"
        "- Keep it concise but useful, usually 2-4 sentences.\n"
        "- If the answer cannot be supported by the context, say 'Not enough data yet.'\n\n"
        f"Context: {json.dumps(payload, sort_keys=True)}"
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are Pulse, the SportLytics analytics assistant. You answer with grounded, evidence-based sports analysis.",
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=220,
        )
        answer = (resp.choices[0].message.content or "").strip() or "Not enough data yet."
    except Exception:
        if requested_codes and len(narrowed) == 2:
            a, b = narrowed[0], narrowed[1]
            answer = (
                f"{a['label']} vs {b['label']}: recent margin delta is {a.get('margin_delta')} versus {b.get('margin_delta')}, "
                f"and offensive delta is {a.get('offense_delta')} versus {b.get('offense_delta')}."
            )
        else:
            best = sorted(summaries, key=lambda s: s.get("margin_delta") or -999, reverse=True)[:3]
            answer = "Top recent movers by margin delta: " + ", ".join(
                f"{row['team_code']} ({row.get('margin_delta')})" for row in best
            )

    result = {
        "assistant_name": "Pulse",
        "answer": answer,
        "supporting_items": narrowed[:5],
        "storylines": storylines,
    }
    _cache_set(cache_key, json.dumps(result), QUERY_TTL_SECONDS)
    return result
