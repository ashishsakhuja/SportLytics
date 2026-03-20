from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

import sqlalchemy as sa

from app.db import SessionLocal
from app.models import ContentItem, Game, TeamGameStats
from app.scripts.ingest_mlb import ingest_range as ingest_mlb_range
from app.scripts.ingest_nba import ingest_range as ingest_nba_range
from app.scripts.ingest_nfl import ingest_nfl_season
from app.scripts.ingest_nhl import ingest_range as ingest_nhl_range
from app.services.espn_summary import fetch_espn_summary, parse_team_boxscore_stats
from app.services.run_ingest import run_all as run_news_ingest

SUPPORTED_SPORTS = ("nfl", "nba", "mlb", "nhl")


@dataclass
class TaskResult:
    name: str
    ok: bool
    detail: str = ""


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def _parse_sports(raw: str | None) -> list[str]:
    if not raw:
        return list(SUPPORTED_SPORTS)
    sports = [s.strip().lower() for s in raw.split(",") if s.strip()]
    bad = [s for s in sports if s not in SUPPORTED_SPORTS]
    if bad:
        raise SystemExit(f"Unsupported sports: {', '.join(bad)}. Use only: {', '.join(SUPPORTED_SPORTS)}")
    return sports


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%d").date()


def _infer_nfl_season(today: date) -> int:
    return today.year if today.month >= 7 else today.year - 1


def _infer_nfl_season_types(today: date) -> list[str]:
    m = today.month
    if m in (7, 8):
        return ["PRE"]
    if m in (9, 10, 11, 12):
        return ["REG"]
    if m in (1, 2):
        return ["REG", "POST"]
    return ["POST"]


async def _run_nfl(season: int, season_types: Iterable[str]) -> None:
    for st in season_types:
        log(f"NFL ingest starting season={season} type={st}")
        await ingest_nfl_season(season=season, season_type=st)
        log(f"NFL ingest finished season={season} type={st}")


async def _run_dated_sport(sport: str, start: date, end: date) -> None:
    log(f"{sport.upper()} ingest starting range={start.isoformat()}..{end.isoformat()}")
    if sport == "nba":
        await ingest_nba_range(start=start, end=end)
    elif sport == "mlb":
        await ingest_mlb_range(start=start, end=end, sleep_s=0.0)
    elif sport == "nhl":
        await ingest_nhl_range(start=start, end=end)
    else:
        raise ValueError(f"Unsupported dated sport: {sport}")
    log(f"{sport.upper()} ingest finished range={start.isoformat()}..{end.isoformat()}")


async def _refresh_recent_team_game_stats(
    *,
    sports: Iterable[str],
    lookback_days: int,
    only_final: bool,
    per_call_sleep: float,
) -> int:
    now = datetime.utcnow()
    start_dt = now - timedelta(days=lookback_days)

    db = SessionLocal()
    try:
        q = db.query(Game).filter(Game.sport.in_(list(sports)), Game.game_date >= start_dt, Game.game_date <= now)
        if only_final:
            q = q.filter(Game.status == "final")
        else:
            q = q.filter(Game.status.in_(["live", "final"]))
        games = q.order_by(Game.game_date.asc().nulls_last(), Game.id.asc()).all()
    finally:
        db.close()

    log(
        f"TEAM_GAME_STATS refresh starting games={len(games)} sports={','.join(sports)} "
        f"lookback_days={lookback_days} only_final={only_final}"
    )

    touched_total = 0
    for idx, game in enumerate(games, start=1):
        event_id = _extract_event_id(sport=game.sport, external_game_id=game.external_game_id)
        try:
            payload = await fetch_espn_summary(sport=game.sport, event_id=event_id)
            per_team = parse_team_boxscore_stats(payload, sport=game.sport)
        except Exception as e:
            log(f"TEAM_GAME_STATS failed game_id={game.id} sport={game.sport} event_id={event_id}: {e}")
            continue

        if not per_team:
            continue

        db2 = SessionLocal()
        try:
            for team_code, stats in per_team.items():
                existing = (
                    db2.query(TeamGameStats)
                    .filter(
                        TeamGameStats.sport == game.sport,
                        TeamGameStats.game_id == game.id,
                        TeamGameStats.team_code == team_code,
                    )
                    .one_or_none()
                )
                if existing is None:
                    db2.add(
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
                else:
                    existing.season = game.season
                    existing.season_type = game.season_type
                    existing.stats = stats
                    existing.source = "espn_summary"
                touched_total += 1
            db2.commit()
        finally:
            db2.close()

        if per_call_sleep > 0:
            await asyncio.sleep(per_call_sleep)

        if idx % 25 == 0:
            log(f"TEAM_GAME_STATS progress processed={idx}/{len(games)} touched_total={touched_total}")

    log(f"TEAM_GAME_STATS refresh finished processed={len(games)} touched_total={touched_total}")
    return touched_total


def _extract_event_id(*, sport: str, external_game_id: str) -> str:
    sport = (sport or "").lower().strip()
    s = str(external_game_id or "").strip()
    if sport == "nfl" and "-" in s:
        return s.split("-", 1)[1]
    return s


def _run_news() -> int:
    db = SessionLocal()
    try:
        before = db.query(sa.func.count(ContentItem.id)).scalar() or 0
        inserted = int(run_news_ingest(db) or 0)
        after = db.query(sa.func.count(ContentItem.id)).scalar() or 0
        log(f"NEWS ingest finished inserted={inserted} total_items={after} delta={after - before}")
        return inserted
    finally:
        db.close()


async def main_async(args) -> int:
    today = datetime.utcnow().date()
    sports = _parse_sports(args.sports)

    start = _parse_date(args.from_date) or (today - timedelta(days=args.days_back))
    end = _parse_date(args.to_date) or (today + timedelta(days=args.days_forward))
    if start > end:
        raise SystemExit("Resolved start date is after end date.")

    nfl_season = args.nfl_season or _infer_nfl_season(today)
    nfl_types = [s.strip().upper() for s in (args.nfl_season_types or ",".join(_infer_nfl_season_types(today))).split(",") if s.strip()]

    log(
        "SYNC_LATEST starting "
        f"sports={','.join(sports)} start={start.isoformat()} end={end.isoformat()} "
        f"news={'no' if args.skip_news else 'yes'} stats={'no' if args.skip_stats else 'yes'}"
    )

    results: list[TaskResult] = []

    for sport in sports:
        try:
            if sport == "nfl":
                await _run_nfl(nfl_season, nfl_types)
                results.append(TaskResult(name=f"games:{sport}", ok=True, detail=f"season={nfl_season} types={','.join(nfl_types)}"))
            else:
                await _run_dated_sport(sport, start, end)
                results.append(TaskResult(name=f"games:{sport}", ok=True, detail=f"range={start.isoformat()}..{end.isoformat()}"))
        except Exception as e:
            results.append(TaskResult(name=f"games:{sport}", ok=False, detail=str(e)))
            log(f"ERROR games:{sport}: {e}")
            if args.strict:
                break

    if not args.skip_news and (not args.strict or all(r.ok for r in results)):
        try:
            inserted = _run_news()
            results.append(TaskResult(name="news", ok=True, detail=f"inserted={inserted}"))
        except Exception as e:
            results.append(TaskResult(name="news", ok=False, detail=str(e)))
            log(f"ERROR news: {e}")
            if args.strict:
                return 1

    if not args.skip_stats and (not args.strict or all(r.ok for r in results)):
        try:
            touched = await _refresh_recent_team_game_stats(
                sports=sports,
                lookback_days=args.stats_lookback_days,
                only_final=args.stats_only_final,
                per_call_sleep=args.stats_sleep,
            )
            results.append(TaskResult(name="team_game_stats", ok=True, detail=f"touched={touched}"))
        except Exception as e:
            results.append(TaskResult(name="team_game_stats", ok=False, detail=str(e)))
            log(f"ERROR team_game_stats: {e}")
            if args.strict:
                return 1

    log("SYNC_LATEST summary:")
    failures = 0
    for r in results:
        status = "OK" if r.ok else "FAILED"
        if not r.ok:
            failures += 1
        log(f"  - {status:<6} {r.name} {r.detail}")

    log(f"SYNC_LATEST done failures={failures}")
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Single command to sync latest games, news, and recent team-game stats for SportLytics."
    )
    p.add_argument("--sports", type=str, default="nfl,nba,mlb,nhl", help="Comma-separated sports to sync.")
    p.add_argument("--from-date", type=str, default=None, help="Override start date for NBA/MLB/NHL in YYYY-MM-DD.")
    p.add_argument("--to-date", type=str, default=None, help="Override end date for NBA/MLB/NHL in YYYY-MM-DD.")
    p.add_argument("--days-back", type=int, default=3, help="Default dated-sport lookback window when --from-date is omitted.")
    p.add_argument("--days-forward", type=int, default=7, help="Default dated-sport lookahead window when --to-date is omitted.")
    p.add_argument("--nfl-season", type=int, default=None, help="Override NFL season year. Defaults to inferred current season.")
    p.add_argument(
        "--nfl-season-types",
        type=str,
        default=None,
        help="Comma-separated NFL season types. Defaults to a month-based auto choice like REG or REG,POST.",
    )
    p.add_argument("--skip-news", action="store_true", help="Skip news RSS ingest.")
    p.add_argument("--skip-stats", action="store_true", help="Skip recent team_game_stats refresh.")
    p.add_argument(
        "--stats-lookback-days",
        type=int,
        default=10,
        help="Refresh team_game_stats for live/final games in the last N days.",
    )
    p.add_argument(
        "--stats-only-final",
        action="store_true",
        help="Only refresh team_game_stats for final games, not live ones.",
    )
    p.add_argument(
        "--stats-sleep",
        type=float,
        default=0.15,
        help="Sleep between ESPN summary calls for recent team_game_stats refresh.",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit on the first task failure instead of continuing with the rest.",
    )
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    code = asyncio.run(main_async(args))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
