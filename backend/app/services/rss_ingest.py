import feedparser
import httpx
from dateutil import parser as dtparser
from datetime import timezone
from sqlalchemy.orm import Session
from ..models import ContentItem
import re
from typing import Optional
from app.services.quality import quality_gate, normalize_title, normalize_snippet

from app.services.enrich import (
    classify_topics,
    compute_rank_score,
    compute_urgency,
    extract_teams,
    make_canonical_id,
    make_dedupe_group_id,
    source_tier,
    build_entities,
)

# Order matters: more specific first
SPORT_RULES = [
    ("cfb", [r"\bcollege football\b", r"\bncaa football\b", r"\bncaaf\b", r"\bcfb\b", r"\bbowl\b", r"\bsec\b", r"\bbig ten\b", r"\bacc\b", r"\bbig 12\b", r"\bpac-?12\b"]),
    ("nfl", [r"\bnfl\b", r"\bsuper bowl\b", r"\bplayoffs\b", r"\bquarterback\b", r"\btouchdown\b", r"\bqb\b", r"\bafc\b", r"\bnfc\b"]),
    ("nba", [r"\bnba\b", r"\bplayoffs\b", r"\bfinals\b", r"\btrade deadline\b", r"\ball-?star\b", r"\b3-?pointer\b"]),
    ("nhl", [r"\bnhl\b", r"\bstanley cup\b", r"\bpower play\b", r"\bgoalie\b", r"\bpuck\b"]),
    ("mlb", [r"\bmlb\b", r"\bhome run\b", r"\bpitcher\b", r"\binnings?\b", r"\bworld series\b", r"\bspring training\b"]),
    ("f1",  [r"\bformula 1\b", r"\bf1\b", r"\bgrand prix\b", r"\bqualifying\b", r"\bpole\b", r"\bpaddock\b"]),
    ("nascar", [r"\bnascar\b", r"\bdaytona\b", r"\b(indycar|indy car)\b", r"\btrack\b", r"\bpit road\b"]),
]

# Team/league token hints help disambiguate
URL_HINTS = {
    "nba": ["/nba", "nba."],
    "nfl": ["/nfl", "nfl."],
    "cfb": ["/college-football", "/ncf", "ncaaf", "collegefootball"],
    "mlb": ["/mlb", "mlb."],
    "nhl": ["/nhl", "nhl."],
    "f1": ["/f1", "formula1", "f1."],
    "nascar": ["/nascar", "nascar."],
}

def classify_sport(title: str, snippet: Optional[str], url: Optional[str]) -> Optional[str]:
    text = f"{title or ''} {snippet or ''}".lower()

    # URL hints first (fast + often accurate)
    if url:
        u = url.lower()
        for sport, hints in URL_HINTS.items():
            if any(h in u for h in hints):
                return sport

    # Keyword rules
    for sport, patterns in SPORT_RULES:
        if any(re.search(p, text) for p in patterns):
            return sport

    return None


def ingest_feed(db: Session, feed_url: str, source: str, sport: str):
    headers = {
        "User-Agent": "SportLyticsBot/1.0 (RSS aggregator; contact: you@example.com)",
        "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.1",
        "Accept-Encoding": "identity",
    }

    with httpx.Client(follow_redirects=True, timeout=20, headers=headers) as client:
        resp = client.get(feed_url)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)  # ✅ bytes, not resp.text

    if "nbcsports" in feed_url:
        print("[NBC DEBUG] status=", resp.status_code, "content-type=", resp.headers.get("content-type"))
        print("[NBC DEBUG] first_200=", resp.content[:200])

    if getattr(parsed, "bozo", False):
        print(f"[RSS PARSE WARNING] source={source} sport={sport} url={feed_url}")
        print(f"  bozo_exception={getattr(parsed, 'bozo_exception', None)}")
    print(f"[RSS] source={source} sport={sport} entries={len(getattr(parsed, 'entries', []))} url={feed_url}")

    inserted = 0
    for e in parsed.entries:
        url = getattr(e, "link", None)
        title = getattr(e, "title", None)
        if not url or not title:
            continue

        # published
        published_raw = getattr(e, "published", None) or getattr(e, "updated", None)
        if not published_raw:
            continue

        TZINFOS = {
            "EST": -5 * 3600,
            "EDT": -4 * 3600,
            "CST": -6 * 3600,
            "CDT": -5 * 3600,
            "MST": -7 * 3600,
            "MDT": -6 * 3600,
            "PST": -8 * 3600,
            "PDT": -7 * 3600,
        }

        dt = dtparser.parse(published_raw, tzinfos=TZINFOS)

        # normalize to UTC (store UTC in DB)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        published_at = dt.astimezone(timezone.utc).replace(tzinfo=None)  # store as naive UTC

        snippet = getattr(e, "summary", None) or ""

        # dedupe by url (unique constraint)
        exists = db.query(ContentItem).filter(ContentItem.url == url).first()
        if exists:
            continue

        effective_sport = sport
        if sport in ("general", "top"):
            inferred = classify_sport(title, snippet, url)
            if inferred:
                effective_sport = inferred

        # ----------------------------
        # Quality gate (Phase 3.3)
        # ----------------------------
        decision = quality_gate(title=title, url=url, snippet=snippet)
        if not decision.ok:
            # Optional: uncomment for debugging drops
            # print(f"[DROP] reason={decision.reason} source={source} title={title[:80]!r}")
            continue

        # Normalize text before enrichment + storage
        title = normalize_title(title)
        snippet = normalize_snippet(snippet) or ""


        # ----------------------------
        # Enrichment + ranking (NEW)
        # ----------------------------
        summary_text = (snippet or "").strip()

        teams = extract_teams(title, summary_text, url=url)
        teams = [t.upper() for t in teams]
        topics = classify_topics(title, summary_text)

        dedupe_group_id = make_dedupe_group_id(title, teams=teams)
        canonical_id = make_canonical_id(dedupe_group_id)

        tier = source_tier(source)
        urgency = compute_urgency(published_at, topics)

        # Duplicate story cluster detection (separate from URL dedupe)
        existing_cluster = (
            db.query(ContentItem)
            .filter(ContentItem.dedupe_group_id == dedupe_group_id)
            .first()
        )
        is_duplicate = existing_cluster is not None

        rank_score = compute_rank_score(published_at, tier, urgency, is_duplicate)

        entities = build_entities(
            teams=teams,
            players=[],
            leagues=[effective_sport] if effective_sport else [],
        )

        # Debug line so you can SEE it working during ingestion
        print(
            f"[ENRICH] source={source} sport={effective_sport} dup={is_duplicate} "
            f"tier={tier} urg={urgency:.2f} rank={rank_score:.2f} "
            f"topics={topics} teams={teams} title={title[:80]!r}"
        )

        db.add(ContentItem(
            source=source,
            sport=effective_sport,
            teams=teams,
            title=title[:300],
            url=url[:600],
            published_at=published_at,
            snippet=snippet,

            # NEW FIELDS
            canonical_id=canonical_id,
            dedupe_group_id=dedupe_group_id,
            topics=topics,
            urgency=urgency,
            sentiment=None,
            entities=entities,
            summary=summary_text[:800] if summary_text else None,
            key_points=None,
            confidence=0.6,  # MVP constant (we can improve later)
            source_tier=tier,
            rank_score=rank_score,
            is_duplicate=is_duplicate,
        ))
        inserted += 1

    db.commit()
    return inserted
