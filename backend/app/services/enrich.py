from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.services.team_aliases import TEAM_ALIASES

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
# backend/app/services/team_aliases.py
TEAM_ALIASES = {k.lower(): v.upper() for k, v in TEAM_ALIASES.items()}



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


import html
import re
from typing import List, Optional

# Optional: precompile alias patterns once for speed (recommended)
# Build this once at import time.
# TEAM_ALIASES: Dict[str, str]  # alias -> code (e.g., "los angeles lakers" -> "LAL")

def _normalize_for_team_match(s: str) -> str:
    if not s:
        return ""
    # Decode HTML entities (&amp;, &#8217;, etc.)
    s = html.unescape(s)

    # Normalize quotes/dashes that commonly appear in feeds
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2013", "-").replace("\u2014", "-")

    s = s.lower()

    # URLs: treat separators as spaces so slug tokens become matchable
    # keep alphanumerics, replace everything else with spaces
    s = re.sub(r"[^a-z0-9]+", " ", s)

    # collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _alias_to_pattern(alias: str) -> re.Pattern:
    """
    Convert an alias like "l.a. lakers" or "san-francisco 49ers" into a robust regex
    that matches regardless of punctuation/spacing (since we normalize to spaces).
    """
    a = _normalize_for_team_match(alias)

    # Turn spaces into flexible whitespace
    # Example: "san francisco 49ers" -> r"\bsan\s+francisco\s+49ers\b"
    parts = [re.escape(p) for p in a.split() if p]
    if not parts:
        # should never happen, but avoid crashing
        return re.compile(r"$^")
    pat = r"\b" + r"\s+".join(parts) + r"\b"
    return re.compile(pat)


# Precompile patterns once (do this at module load)
# NOTE: order matters; we preserve insertion order of TEAM_ALIASES
_TEAM_PATTERNS: List[tuple[re.Pattern, str]] = [
    (_alias_to_pattern(alias), abbr) for alias, abbr in TEAM_ALIASES.items()
]


def extract_teams(title: str, summary: str = "", url: Optional[str] = None) -> List[str]:
    # Combine text sources
    combined = f"{title or ''} {summary or ''} {url or ''}"
    text = _normalize_for_team_match(combined)

    found: List[str] = []

    # 1) Alias/name/nickname detection (most reliable)
    for pat, abbr in _TEAM_PATTERNS:
        if pat.search(text):
            found.append(abbr)

    # 2) Direct code detection fallback (helps when feeds include abbreviations)
    # Only add codes that exist anywhere in TEAM_ALIASES values (avoid random 3-letter words)
    valid_codes = set(TEAM_ALIASES.values())

    # After normalization, codes appear as tokens (e.g., "sf", "lal")
    # We'll scan original (not stripped of caps) by using normalized text and uppercase.
    for token in text.split():
        if len(token) in (2, 3, 4):  # KC, SF, LAL, etc.
            code = token.upper()
            if code in valid_codes:
                found.append(code)

    # Deduplicate preserving order
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
