from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


BAD_TITLE_SUBSTRINGS = [
    "subscribe",
    "newsletter",
    "sign up",
    "shop",
    "merch",
    "tickets",
    "watch live",
    "podcast:",
    "advertisement",
]

BAD_DOMAINS = [
    # add any noisy domains you notice
]


def _norm_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def normalize_title(title: Optional[str]) -> str:
    title = title or ""
    return _norm_spaces(title)


def normalize_snippet(snippet: Optional[str]) -> Optional[str]:
    if not snippet:
        return None
    snippet = _norm_spaces(snippet)
    return snippet or None


def domain_from_url(url: str) -> str:
    # lightweight parse; good enough
    m = re.search(r"https?://([^/]+)/?", url or "")
    return (m.group(1).lower() if m else "")


@dataclass
class QualityDecision:
    ok: bool
    reason: Optional[str] = None


def quality_gate(
    *,
    title: Optional[str],
    url: Optional[str],
    snippet: Optional[str],
) -> QualityDecision:
    """
    Return ok=False to drop the item during ingestion.
    """
    title_n = normalize_title(title)
    if not title_n:
        return QualityDecision(False, "missing_title")

    if len(title_n) < 15:
        return QualityDecision(False, "title_too_short")

    t_low = title_n.lower()
    for bad in BAD_TITLE_SUBSTRINGS:
        if bad in t_low:
            return QualityDecision(False, f"bad_title:{bad}")

    if not url:
        return QualityDecision(False, "missing_url")

    dom = domain_from_url(url)
    if dom and any(dom.endswith(b) or dom == b for b in BAD_DOMAINS):
        return QualityDecision(False, f"bad_domain:{dom}")

    # If snippet is totally empty and title looks like boilerplate, drop
    s_n = normalize_snippet(snippet)
    if (s_n is None) and any(x in t_low for x in ["video", "highlights", "recap", "score"]):
        # tweak as you see fit
        return QualityDecision(False, "low_info_no_snippet")

    return QualityDecision(True, None)
