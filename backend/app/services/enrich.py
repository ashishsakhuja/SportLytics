from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


PUNCT_RE = re.compile(r"[^a-z0-9\s]")
WS_RE = re.compile(r"\s+")

TOPIC_RULES = {
    "injury": [r"\binjur", r"\bout\b", r"\bquestionable\b", r"\bdoubtful\b", r"\bday-to-day\b", r"\bir\b"],
    "trade": [r"\btrade\b", r"\btraded\b", r"\bblockbuster\b", r"\bdeal\b", r"\bacquire\b", r"\bsigns?\b"],
    "betting": [r"\bodds\b", r"\bspread\b", r"\bline\b", r"\bparlay\b", r"\bover/under\b", r"\bo/u\b"],
    "analysis": [r"\banalysis\b", r"\bbreakdown\b", r"\bfilm\b", r"\bwhat it means\b", r"\bpreview\b"],
    "suspension": [r"\bsuspend", r"\bfined\b", r"\bdiscipline\b"],
}

# Start simple. You can expand this later.
TEAM_ALIASES = {
    # NBA examples
    "lakers": "LAL",
    "celtics": "BOS",
    "warriors": "GSW",
    "knicks": "NYK",
    "sixers": "PHI",
    "76ers": "PHI",
    # NFL examples
    "chiefs": "KC",
    "eagles": "PHI",
    "cowboys": "DAL",
    "49ers": "SF",
}


def _utc_now() -> datetime:
    # return naive UTC to match DB convention (published_at stored as naive UTC)
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_title(title: str) -> str:
    t = (title or "").lower().strip()
    t = PUNCT_RE.sub(" ", t)
    t = WS_RE.sub(" ", t).strip()
    return t


def make_dedupe_group_id(title: str, teams: Optional[List[str]] = None) -> str:
    base = normalize_title(title)
    if teams:
        base += "|" + "|".join(sorted([t.lower() for t in teams]))
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def make_canonical_id(dedupe_group_id: str) -> str:
    # MVP: canonical = dedupe_group_id
    return dedupe_group_id


def classify_topics(title: str, summary: str = "") -> List[str]:
    text = f"{title} {summary}".lower()
    topics: List[str] = []
    for topic, patterns in TOPIC_RULES.items():
        for p in patterns:
            if re.search(p, text):
                topics.append(topic)
                break
    return topics


def extract_teams(title: str, summary: str = "") -> List[str]:
    text = f"{title} {summary}".lower()
    found: List[str] = []
    for alias, abbr in TEAM_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", text):
            found.append(abbr)
    # dedupe preserving order
    out: List[str] = []
    for t in found:
        if t not in out:
            out.append(t)
    return out


def source_tier(source: str) -> int:
    s = (source or "").lower()
    if any(x in s for x in ["ap", "associated press", "reuters", "espn", "the athletic"]):
        return 1
    if any(x in s for x in ["yahoo", "cbs", "nbc", "fox", "bleacher report"]):
        return 2
    return 3


def compute_urgency(published_at: Optional[datetime], topics: List[str]) -> float:
    if not published_at:
        return 0.0
    now = _utc_now()
    age_hours = max(0.0, (now - published_at).total_seconds() / 3600.0)
    recency = max(0.0, 1.0 - (age_hours / 24.0))  # fades over 24h

    bump = 0.0
    if "injury" in topics:
        bump += 0.15
    if "trade" in topics:
        bump += 0.15
    if "suspension" in topics:
        bump += 0.10

    return min(1.0, recency + bump)


def compute_rank_score(published_at: Optional[datetime], tier: int, urgency: float, is_duplicate: bool) -> float:
    now = _utc_now()
    if not published_at:
        rec = 0.0
    else:
        age_hours = max(0.0, (now - published_at).total_seconds() / 3600.0)
        rec = max(0.0, 1.0 - (age_hours / 48.0))  # fades over 48h

    tier_bonus = {1: 0.25, 2: 0.10, 3: 0.0}.get(tier, 0.0)
    dup_penalty = 0.35 if is_duplicate else 0.0

    return float(rec + tier_bonus + (urgency * 0.6) - dup_penalty)


def build_entities(teams: List[str], players: Optional[List[str]] = None, leagues: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "teams": teams or [],
        "players": players or [],
        "leagues": leagues or [],
    }
