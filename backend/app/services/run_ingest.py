from sqlalchemy.orm import Session
from .rss_ingest import ingest_feed

FEEDS = [
    ("ESPN", "nba", "https://www.espn.com/espn/rss/nba/news"),
    ("ESPN", "nfl", "https://www.espn.com/espn/rss/nfl/news"),
    ("ESPN", "cfb", "https://www.espn.com/espn/rss/ncf/news"),
    ("ESPN", "mlb", "https://www.espn.com/espn/rss/mlb/news"),
    ("ESPN", "nhl", "https://www.espn.com/espn/rss/nhl/news"),
    # Optional:
    ("ESPN", "top", "https://www.espn.com/espn/rss/news"),

    # Yahoo Sports (general → classify by keywords later)
    ("Yahoo Sports", "general", "https://sports.yahoo.com/rss/"),

    # CBS Sports
    ("CBS Sports", "nba", "https://www.cbssports.com/rss/headlines/nba/"),
    ("CBS Sports", "nfl", "https://www.cbssports.com/rss/headlines/nfl/"),
    ("CBS Sports", "cfb", "https://www.cbssports.com/rss/headlines/college-football/"),
    ("CBS Sports", "mlb", "https://www.cbssports.com/rss/headlines/mlb/"),
    ("CBS Sports", "nhl", "https://www.cbssports.com/rss/headlines/nhl/"),

    # SI - 404 ERROR
    # ("Sports Illustrated", "general", "https://www.si.com/rss/si_topstories.rss"),

    # NBC Sports - WRONG FORMAT (HTML) ERROR
    # ("NBC Sports", "general", "https://sports.nbcsports.com/feed/"),

    # Fox Sports

]


def run_all(db: Session):
    total = 0
    for source, sport, url in FEEDS:
        try:
            inserted = ingest_feed(db, url, source=source, sport=sport)
            print(f"[INGEST] {source} {sport}: inserted={inserted}")
            total += inserted
        except Exception as e:
            print(f"[INGEST ERROR] {source} {sport} url={url} err={e}")
            continue
    return total

