from __future__ import annotations

import argparse
import asyncio
import time
from typing import Optional

import sqlalchemy as sa

from app.db import SessionLocal
from app.models import Game, TeamGameStats
from app.services.espn_summary import fetch_espn_summary, parse_team_boxscore_stats


def _extract_event_id(*, sport: str, external_game_id: str) -> str:
    """
    NBA/MLB/NHL: external_game_id is usually ESPN event id already.
    NFL: you store as "{season}-{espn_id}" -> need the tail espn_id.
    """
    sport = (sport or "").lower().strip()
    s = str(external_game_id or "").strip()
    if sport == "nfl" and "-" in s:
        return s.split("-", 1)[1]
    return s


def _already_has_stats(db, *, sport: str, game_id: int) -> bool:
    return (
        db.query(sa.func.count(TeamGameStats.id))
        .filter(TeamGameStats.sport == sport, TeamGameStats.game_id == game_id)
        .scalar()
        or 0
    ) > 0


async def _run_one(game: Game, *, sleep_s: float) -> int:
    event_id = _extract_event_id(sport=game.sport, external_game_id=game.external_game_id)
    payload = await fetch_espn_summary(sport=game.sport, event_id=event_id)
    per_team = parse_team_boxscore_stats(payload, sport=game.sport)

    db = SessionLocal()
    try:
        inserted = 0
        for team_code, stats in per_team.items():
            existing = (
                db.query(TeamGameStats)
                .filter(
                    TeamGameStats.sport == game.sport,
                    TeamGameStats.game_id == game.id,
                    TeamGameStats.team_code == team_code,
                )
                .one_or_none()
            )
            if existing is None:
                db.add(
                    TeamGameStats(
                        sport=game.sport,
                        game_id=game.id,
                        team_code=team_code,
                        season=game.season,
                        season_type=game.season_type,
                        stats=stats,
                        source="espn_summary",
                    )
                )
                inserted += 1
            else:
                existing.season = game.season
                existing.season_type = game.season_type
                existing.stats = stats
                existing.source = "espn_summary"
        db.commit()
        if sleep_s > 0:
            time.sleep(sleep_s)
        return inserted
    finally:
        db.close()


async def main_async(args) -> None:
    db = SessionLocal()
    try:
        q = db.query(Game).filter(Game.sport == args.sport)

        if args.season_from is not None:
            q = q.filter(Game.season >= args.season_from)
        if args.season_to is not None:
            q = q.filter(Game.season <= args.season_to)
        if args.season_type is not None:
            q = q.filter(Game.season_type == args.season_type)

        # Only backfill finished games by default (fewer missing stats/partial)
        if args.only_final:
            q = q.filter(Game.status == "final")

        q = q.order_by(Game.game_date.asc().nulls_last(), Game.id.asc())
        games = q.all()

        print(f"[STATS] sport={args.sport} games_found={len(games)} (filters applied)")

    finally:
        db.close()

    inserted_total = 0
    processed = 0

    # sequential (safe + simple)
    for g in games:
        processed += 1
        db2 = SessionLocal()
        try:
            if args.skip_existing and _already_has_stats(db2, sport=g.sport, game_id=g.id):
                if processed % 500 == 0:
                    print(f"[STATS] processed={processed} inserted_total={inserted_total} (skipping existing)")
                continue
        finally:
            db2.close()

        try:
            ins = await _run_one(g, sleep_s=args.sleep)
            inserted_total += ins
        except Exception as e:
            print(f"[STATS] game_id={g.id} ext={g.external_game_id} FAILED: {e}")

        if processed % 200 == 0:
            print(f"[STATS] processed={processed}/{len(games)} inserted_total={inserted_total}")

    print(f"[STATS] DONE sport={args.sport} processed={processed} inserted_total={inserted_total}")


def main() -> None:
    p = argparse.ArgumentParser(description="Backfill per-team per-game ESPN summary stats into team_game_stats.")
    p.add_argument("--sport", required=True, choices=["nfl", "nba", "mlb", "nhl"])
    p.add_argument("--season-from", type=int, default=None)
    p.add_argument("--season-to", type=int, default=None)
    p.add_argument("--season-type", type=str, default=None, help="REG/POST/PRE (optional)")
    p.add_argument("--sleep", type=float, default=0.25, help="Sleep between ESPN calls (seconds).")
    p.add_argument("--skip-existing", action="store_true", help="Skip games that already have stats rows.")
    p.add_argument("--only-final", action="store_true", help="Only process games with status=final.")
    args = p.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()