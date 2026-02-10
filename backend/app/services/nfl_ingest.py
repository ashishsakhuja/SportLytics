from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models import Game, StandingsSnapshot, Team
from app.services.nfl_provider import NFLGameRow


# Normalize legacy/alternate abbreviations that sometimes show up in feeds
_TEAM_CODE_NORMALIZE = {
    "JAC": "JAX",
    "STL": "LAR",
    "SD": "LAC",
    "OAK": "LV",
    "WSH": "WAS",
    "LA": "LAR",  # sometimes ambiguous; treat as Rams for modern seasons
}


def normalize_team_code(code: str) -> str:
    c = (code or "").strip().upper()
    return _TEAM_CODE_NORMALIZE.get(c, c)


def ensure_team_stub(db: Session, *, sport: str, team_code: str) -> None:
    """Create a minimal Team row if it doesn't exist yet."""
    team_code = normalize_team_code(team_code)
    existing = db.query(Team).filter(Team.sport == sport, Team.team_code == team_code).one_or_none()
    if existing:
        return
    db.add(Team(sport=sport, team_code=team_code, name=team_code, city=None, meta=None))


def upsert_game_from_row(
    db: Session,
    *,
    row: NFLGameRow,
    provider: str = "nfl_scorestrip",
) -> None:
    """Upsert a Game from a parsed NFLGameRow."""

    home = normalize_team_code(row.home)
    away = normalize_team_code(row.away)
    ensure_team_stub(db, sport="nfl", team_code=home)
    ensure_team_stub(db, sport="nfl", team_code=away)

    game = (
        db.query(Game)
        .filter(
            Game.sport == "nfl",
            Game.provider == provider,
            Game.external_game_id == row.eid,
        )
        .one_or_none()
    )

    payload = {
        "eid": row.eid,
        "season": row.season,
        "season_type": row.season_type,
        "week": row.week,
        "game_date": row.game_date.isoformat() if row.game_date else None,
        "home": home,
        "away": away,
        "home_score": row.home_score,
        "away_score": row.away_score,
        "status": row.status,
        "phase": row.phase,
        "source_url": row.source_url,
    }

    if not game:
        db.add(
            Game(
                sport="nfl",
                season=row.season,
                season_type=row.season_type,
                week=row.week,
                provider=provider,
                external_game_id=row.eid,
                game_date=row.game_date,
                home_team_code=home,
                away_team_code=away,
                home_score=row.home_score,
                away_score=row.away_score,
                status=row.status,
                phase=row.phase,
                source_url=row.source_url,
                raw=payload,
                updated_at=datetime.utcnow(),
            )
        )
        return

    game.season = row.season
    game.season_type = row.season_type
    game.week = row.week
    game.game_date = row.game_date
    game.home_team_code = home
    game.away_team_code = away
    game.home_score = row.home_score
    game.away_score = row.away_score
    game.status = row.status
    game.phase = row.phase
    game.source_url = row.source_url
    game.raw = payload
    game.updated_at = datetime.utcnow()


def write_standings_snapshot(
    db: Session,
    *,
    season: int,
    season_type: str,
    as_of: datetime,
    rows: Iterable[dict],
    source_url: Optional[str] = None,
) -> None:
    """Insert a standings snapshot (append-only)."""

    for r in rows:
        team_code = normalize_team_code(r.get("team_code") or "")
        if not team_code:
            continue
        ensure_team_stub(db, sport="nfl", team_code=team_code)

        db.add(
            StandingsSnapshot(
                sport="nfl",
                season=season,
                season_type=season_type,
                as_of=as_of,
                team_code=team_code,
                conference=r.get("conference"),
                division=r.get("division"),
                wins=r.get("wins"),
                losses=r.get("losses"),
                ties=r.get("ties"),
                pct=r.get("pct"),
                rank=r.get("rank"),
                source_url=source_url,
                raw=r.get("raw"),
            )
        )
