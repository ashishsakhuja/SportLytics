from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime, timedelta

from app.db import SessionLocal
from app.services.mlb_provider_espn import fetch_espn_mlb_scoreboard, parse_espn_mlb_scoreboard
from app.services.mlb_ingest import upsert_mlb_game_from_row


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _yyyymmdd(d: date) -> str:
    return d.strftime("%Y%m%d")


async def ingest_range(*, start: date, end: date, sleep_s: float = 0.0) -> None:
    db = SessionLocal()
    try:
        d = start
        total = 0
        days = 0

        while d <= end:
            days += 1
            try:
                payload = await fetch_espn_mlb_scoreboard(date_yyyymmdd=_yyyymmdd(d))
            except Exception as e:
                print(f"[MLB] date={d.isoformat()}: fetch failed: {e}")
                d += timedelta(days=1)
                continue

            rows = parse_espn_mlb_scoreboard(payload)
            for r in rows:
                upsert_mlb_game_from_row(db, row=r)

            db.commit()
            total += len(rows)

            if rows:
                print(f"[MLB] date={d.isoformat()}: upserted {len(rows)} games")

            if sleep_s > 0:
                await asyncio.sleep(sleep_s)

            d += timedelta(days=1)

        print(f"[MLB] DONE days={days} total_games={total}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest MLB games from ESPN scoreboard by date range.")
    parser.add_argument("--from-date", type=str, required=True, help="YYYY-MM-DD")
    parser.add_argument("--to-date", type=str, required=True, help="YYYY-MM-DD")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between days (rate limit).")
    args = parser.parse_args()

    start = _parse_date(args.from_date)
    end = _parse_date(args.to_date)
    if start > end:
        raise SystemExit("--from-date must be <= --to-date")

    asyncio.run(ingest_range(start=start, end=end, sleep_s=args.sleep))


if __name__ == "__main__":
    main()
