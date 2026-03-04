from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models import Game, TeamGameStats


def upsert_team_game_stats(
    db: Session,
    *,
    game: Game,
    team_code: str,
    stats: Dict[str, Any],
    source: str = "espn_summary",
) -> None:
    team_code = (team_code or "").strip().upper()
    if not team_code:
        return

    row = (
        db.query(TeamGameStats)
        .filter(
            TeamGameStats.sport == game.sport,
            TeamGameStats.game_id == game.id,
            TeamGameStats.team_code == team_code,
        )
        .one_or_none()
    )

    if row is None:
        db.add(
            TeamGameStats(
                sport=game.sport,
                game_id=game.id,
                team_code=team_code,
                season=game.season,
                season_type=game.season_type,
                stats=stats,
                source=source,
                ingested_at=datetime.utcnow(),
            )
        )
        return

    row.season = game.season
    row.season_type = game.season_type
    row.stats = stats
    row.source = source
    row.ingested_at = datetime.utcnow()