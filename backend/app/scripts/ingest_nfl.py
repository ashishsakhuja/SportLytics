from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from app.db import SessionLocal
from app.services.nfl_provider_espn import fetch_espn_scoreboard, parse_espn_scoreboard
from app.services.nfl_ingest import upsert_game_from_row, write_standings_snapshot
from app.services.nfl_standings import compute_nfl_standings_from_games


def _season_type_weeks(*, season: int, season_type: str) -> range:
    """
    ESPN's NFL scoreboard uses "week" but the total number of weeks changes
    across eras (e.g., 17-week regular season pre-2021; 18 weeks 2021+).

    Instead of trying to perfectly hardcode every historical nuance (preseason
    and playoffs vary too), we iterate through a safe upper bound and stop early
    once we see empty weeks.
    """
    season_type = season_type.upper().strip()

    # Safe upper bounds (we'll stop early when the feed returns no events).
    if season_type == "REG":
        # 2021+ has 18 regular-season weeks; older seasons generally max at 17.
        # Keep some slack so this works if the feed ever changes.
        return range(1, 23)
    if season_type == "PRE":
        return range(1, 9)
    if season_type == "POST":
        return range(1, 9)
    return range(1, 23)


async def ingest_nfl_season(*, season: int, season_type: str) -> None:
    """Fetch scoreboard week-by-week and upsert games. Then write a standings snapshot."""
    season_type = season_type.upper().strip()
    weeks = _season_type_weeks(season=season, season_type=season_type)

    db = SessionLocal()
    try:
        total_games = 0
        empty_weeks = 0

        for week in weeks:
            try:
                payload = await fetch_espn_scoreboard(week=week, season=season, season_type=season_type)
            except Exception as e:
                print(f"[NFL] season={season} type={season_type} week={week}: fetch failed: {e}")
                continue

            game_rows = parse_espn_scoreboard(payload, season=season, season_type=season_type, week=week)

            # Stop early once we run out of weeks for the season.
            if not game_rows:
                empty_weeks += 1
                # two consecutive empty weeks = we're past the season boundary
                if empty_weeks >= 2:
                    print(f"[NFL] season={season} type={season_type}: no games after week={week}; stopping")
                    break
                print(f"[NFL] season={season} type={season_type} week={week}: no games")
                continue

            empty_weeks = 0

            for row in game_rows:
                upsert_game_from_row(db, row=row)

            db.commit()
            total_games += len(game_rows)
            print(f"[NFL] season={season} type={season_type} week={week}: upserted {len(game_rows)} games")

        import sqlalchemy as sa
        from app.models import Game

        count = (
            db.query(sa.func.count(Game.id))
            .filter(Game.sport == "nfl", Game.season == season, Game.season_type == season_type)
            .scalar()
        )

        if not count:
            print("[NFL] No games ingested; skipping standings snapshot.")
            return

        standings = compute_nfl_standings_from_games(db, season=season, season_type=season_type)
        now = datetime.utcnow()
        write_standings_snapshot(
            db,
            season=season,
            season_type=season_type,
            as_of=now,
            rows=[
                {
                    "team_code": s.team_code,
                    "conference": s.conference,
                    "division": s.division,
                    "wins": s.wins,
                    "losses": s.losses,
                    "ties": s.ties,
                    "pct": s.pct,
                    "rank": s.rank,
                    "raw": {
                        "computed_from": "games",
                        "as_of": now.isoformat() + "Z",
                    },
                }
                for s in standings
            ],
            source_url="https://www.nfl.com/standings/",
        )
        db.commit()

        print(f"[NFL] season={season} type={season_type}: processed ~{total_games} games")
        print(f"[NFL] standings snapshot rows: {len(standings)}")

    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest NFL schedule/scores and compute standings snapshots.")
    parser.add_argument("--season", type=int, help="Single season year (e.g., 2024).")
    parser.add_argument("--season-from", type=int, help="First season year for a range (inclusive).")
    parser.add_argument("--season-to", type=int, help="Last season year for a range (inclusive).")
    parser.add_argument(
        "--seasons",
        type=str,
        help='Comma-separated list of seasons (e.g., "2019,2020,2021"). Overrides --season/--season-from/--season-to.',
    )
    parser.add_argument(
        "--season-types",
        type=str,
        default="REG",
        help='Comma-separated list of season types to ingest: PRE,REG,POST (default "REG").',
    )
    args = parser.parse_args()

    season_types = [s.strip().upper() for s in (args.season_types or "REG").split(",") if s.strip()]
    if not season_types:
        season_types = ["REG"]

    if args.seasons:
        seasons = [int(s.strip()) for s in args.seasons.split(",") if s.strip()]
    elif args.season_from is not None or args.season_to is not None:
        if args.season_from is None or args.season_to is None:
            raise SystemExit("Provide BOTH --season-from and --season-to (inclusive).")
        if args.season_from > args.season_to:
            raise SystemExit("--season-from must be <= --season-to")
        seasons = list(range(args.season_from, args.season_to + 1))
    elif args.season is not None:
        seasons = [args.season]
    else:
        raise SystemExit("Provide --season, --season-from/--season-to, or --seasons")

    async def _run() -> None:
        for season in seasons:
            for st in season_types:
                await ingest_nfl_season(season=season, season_type=st)

    asyncio.run(_run())


if __name__ == "__main__":
    main()
