from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Game, Team
from app.services.mlb_provider_espn import MLBGameRow


def ensure_team(db: Session, *, team_code: str, name: Optional[str] = None, city: Optional[str] = None) -> None:
    team_code = (team_code or "").strip().upper()
    if not team_code:
        return

    # prevent duplicates inside the same session flush
    for obj in db.new:
        if isinstance(obj, Team) and obj.sport == "mlb" and obj.team_code == team_code:
            return

    existing = db.query(Team).filter(Team.sport == "mlb", Team.team_code == team_code).one_or_none()
    if existing:
        if name and (existing.name == existing.team_code or not existing.name):
            existing.name = name
        if city and not existing.city:
            existing.city = city
        return

    db.add(Team(sport="mlb", team_code=team_code, name=name or team_code, city=city, meta=None))


def upsert_mlb_game_from_row(db: Session, *, row: MLBGameRow, provider: str = "espn_mlb") -> None:
    home = (row.home or "").strip().upper()
    away = (row.away or "").strip().upper()

    ensure_team(db, team_code=home)
    ensure_team(db, team_code=away)

    # games.phase is VARCHAR(10) right now → keep it safe
    phase = row.phase
    if phase and len(phase) > 10:
        phase = phase[:10]

    game = (
        db.query(Game)
        .filter(Game.sport == "mlb", Game.provider == provider, Game.external_game_id == row.eid)
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
        "phase": phase,
        "source_url": row.source_url,
    }

    if not game:
        db.add(
            Game(
                sport="mlb",
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
                phase=phase,
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
    game.phase = phase
    game.source_url = row.source_url
    game.raw = payload
    game.updated_at = datetime.utcnow()
