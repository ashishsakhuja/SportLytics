from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Game, Team
from app.services.nba_provider_espn import NBAGameRow


def ensure_team(db: Session, *, team_code: str, name: Optional[str] = None, city: Optional[str] = None) -> None:
    team_code = (team_code or "").strip().upper()
    if not team_code:
        return

    # ✅ IMPORTANT: guard against duplicates in the *current session* (before commit)
    for obj in db.new:
        if isinstance(obj, Team) and obj.sport == "nba" and obj.team_code == team_code:
            return

    existing = db.query(Team).filter(Team.sport == "nba", Team.team_code == team_code).one_or_none()
    if existing:
        # lightly enrich if missing
        if name and (existing.name == existing.team_code or not existing.name):
            existing.name = name
        if city and not existing.city:
            existing.city = city
        return

    db.add(
        Team(
            sport="nba",
            team_code=team_code,
            name=name or team_code,
            city=city,
            meta=None,
        )
    )



def upsert_nba_game_from_row(db: Session, *, row: NBAGameRow, provider: str = "espn_nba") -> None:
    home = (row.home or "").strip().upper()
    away = (row.away or "").strip().upper()

    ensure_team(db, team_code=home)
    ensure_team(db, team_code=away)

    game = (
        db.query(Game)
        .filter(
            Game.sport == "nba",
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
                sport="nba",
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
