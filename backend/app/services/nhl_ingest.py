from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Game, Team
from app.services.nhl_provider_espn import NHLGameRow


def ensure_team(db: Session, *, team_code: str, name: Optional[str] = None, city: Optional[str] = None) -> None:
    team_code = (team_code or "").strip().upper()
    if not team_code:
        return

    # guard against duplicates in current session
    for obj in db.new:
        if isinstance(obj, Team) and obj.sport == "nhl" and obj.team_code == team_code:
            return

    existing = db.query(Team).filter(Team.sport == "nhl", Team.team_code == team_code).one_or_none()
    if existing:
        if name and (existing.name == existing.team_code or not existing.name):
            existing.name = name
        if city and not existing.city:
            existing.city = city
        return

    db.add(
        Team(
            sport="nhl",
            team_code=team_code,
            name=name or team_code,
            city=city,
            meta=None,
        )
    )


def upsert_nhl_game_from_row(db: Session, *, row: NHLGameRow, provider: str = "espn_nhl") -> None:
    home = (row.home or "").strip().upper()
    away = (row.away or "").strip().upper()

    ensure_team(db, team_code=home)
    ensure_team(db, team_code=away)

    game = (
        db.query(Game)
        .filter(
            Game.sport == "nhl",
            Game.provider == provider,
            Game.external_game_id == row.eid,
        )
        .one_or_none()
    )

    payload = {
        "eid": row.eid,
        "season": row.season,
        "season_type": row.season_type,
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
                sport="nhl",
                season=row.season,
                season_type=row.season_type,
                week=None,
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
    game.week = None
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
