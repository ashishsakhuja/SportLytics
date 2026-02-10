from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
import sqlalchemy as sa

from app.models import Game


# Minimal team -> conference/division map (modern NFL alignment)
# Used only for grouping/sorting standings. You can enrich this later in the Team table.
NFL_TEAM_META: Dict[str, Tuple[str, str]] = {
    # AFC East
    "BUF": ("AFC", "East"), "MIA": ("AFC", "East"), "NE": ("AFC", "East"), "NYJ": ("AFC", "East"),
    # AFC North
    "BAL": ("AFC", "North"), "CIN": ("AFC", "North"), "CLE": ("AFC", "North"), "PIT": ("AFC", "North"),
    # AFC South
    "HOU": ("AFC", "South"), "IND": ("AFC", "South"), "JAX": ("AFC", "South"), "TEN": ("AFC", "South"),
    # AFC West
    "DEN": ("AFC", "West"), "KC": ("AFC", "West"), "LV": ("AFC", "West"), "LAC": ("AFC", "West"),

    # NFC East
    "DAL": ("NFC", "East"), "NYG": ("NFC", "East"), "PHI": ("NFC", "East"), "WAS": ("NFC", "East"),
    # NFC North
    "CHI": ("NFC", "North"), "DET": ("NFC", "North"), "GB": ("NFC", "North"), "MIN": ("NFC", "North"),
    # NFC South
    "ATL": ("NFC", "South"), "CAR": ("NFC", "South"), "NO": ("NFC", "South"), "TB": ("NFC", "South"),
    # NFC West
    "ARI": ("NFC", "West"), "LAR": ("NFC", "West"), "SF": ("NFC", "West"), "SEA": ("NFC", "West"),
}


@dataclass
class StandingsRow:
    team_code: str
    conference: Optional[str]
    division: Optional[str]
    wins: int
    losses: int
    ties: int
    pct: float
    rank: Optional[int] = None


def compute_nfl_standings_from_games(db: Session, season: int, season_type: str = "REG") -> List[StandingsRow]:
    """Compute W/L/T standings from finalized games stored in the DB."""

    games = (
        db.query(Game)
        .filter(
            Game.sport == "nfl",
            Game.season == season,
            Game.season_type == season_type,
            Game.status == "final",
            Game.home_score.isnot(None),
            Game.away_score.isnot(None),
        )
        .all()
    )

    rec: Dict[str, Dict[str, int]] = {}

    def ensure(team: str):
        if team not in rec:
            rec[team] = {"w": 0, "l": 0, "t": 0}

    for g in games:
        h, a = g.home_team_code, g.away_team_code
        ensure(h)
        ensure(a)

        if g.home_score > g.away_score:
            rec[h]["w"] += 1
            rec[a]["l"] += 1
        elif g.home_score < g.away_score:
            rec[h]["l"] += 1
            rec[a]["w"] += 1
        else:
            rec[h]["t"] += 1
            rec[a]["t"] += 1

    out: List[StandingsRow] = []
    for team, r in rec.items():
        w, l, t = r["w"], r["l"], r["t"]
        gp = w + l + t
        pct = (w + 0.5 * t) / gp if gp else 0.0
        conf, div = NFL_TEAM_META.get(team, (None, None))
        out.append(
            StandingsRow(
                team_code=team,
                conference=conf,
                division=div,
                wins=w,
                losses=l,
                ties=t,
                pct=round(pct, 3),
            )
        )

    # Sort and assign rank within each (conference, division)
    out.sort(key=lambda x: (x.conference or "", x.division or "", -x.pct, -x.wins, x.losses, x.team_code))

    current_key: Tuple[Optional[str], Optional[str]] | None = None
    rank = 0
    for row in out:
        key = (row.conference, row.division)
        if key != current_key:
            current_key = key
            rank = 1
        else:
            rank += 1
        row.rank = rank

    return out
