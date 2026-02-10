from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from app.db import SessionLocal
from app.services.nfl_provider_espn import fetch_espn_scoreboard, parse_espn_scoreboard
from app.services.nfl_ingest import upsert_game_from_row, write_standings_snapshot
from app.services.nfl_standings import compute_nfl_standings_from_games


def _season_type_weeks(season_type: str) -> range:
    season_type = season_type.upper().strip()
    if season_type == "REG":
        return range(1, 19)  # 18-week regular season
    if season_type == "PRE":
        return range(1, 5)
    if season_type == "POST":
        return range(1, 5)
    return range(1, 19)


async def ingest_nfl_season(*, season: int, season_type: str) -> None:
    """Fetch scorestrip week-by-week and upsert games. Then write a standings snapshot."""

    season_type = season_type.upper().strip()
    weeks = _season_type_weeks(season_type)

    db = SessionLocal()
    try:
        total_games = 0
        for week in weeks:
            try:
                payload = await fetch_espn_scoreboard(week=week, season=season, season_type=season_type)
            except Exception as e:
                print(f"[NFL] season={season} type={season_type} week={week}: fetch failed: {e}")
                continue

            game_rows = parse_espn_scoreboard(payload, season=season, season_type=season_type, week=week)

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

        # standings snapshot from DB (final games only)
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
    parser.add_argument("--season", type=int, required=True, help="Season year (e.g., 2025)")
    parser.add_argument("--season-type", type=str, default="REG", help="PRE | REG | POST")
    args = parser.parse_args()

    asyncio.run(ingest_nfl_season(season=args.season, season_type=args.season_type))


if __name__ == "__main__":
    main()
