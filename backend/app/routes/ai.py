from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.ai_insights_service import answer_query, build_storylines
from app.services.ai_service import generate_chart_caption_cached

router = APIRouter(prefix="/ai", tags=["AI"])


class ChartCaptionRequest(BaseModel):
    chart_id: str
    sport: str
    season: int
    season_type: str
    team: str
    summary: dict


class QueryRequest(BaseModel):
    sport: str
    season: int
    season_type: str = "REG"
    team: str | None = None
    question: str


@router.post("/chart-caption")
def chart_caption(data: ChartCaptionRequest):
    caption = generate_chart_caption_cached(
        chart_id=data.chart_id,
        sport=data.sport,
        season=data.season,
        season_type=data.season_type,
        team=data.team,
        summary=data.summary,
    )
    return {"caption": caption}


@router.get("/storylines")
def get_storylines(
    sport: str,
    season: int,
    season_type: str = "REG",
    team: str | None = None,
    limit: int = 6,
    db: Session = Depends(get_db),
):
    items = build_storylines(
        db,
        sport=sport,
        season=season,
        season_type=season_type,
        team_code=team,
        limit=limit,
    )
    return {
        "assistant_name": "Pulse",
        "sport": sport,
        "season": season,
        "season_type": season_type,
        "team": team,
        "count": len(items),
        "items": items,
    }


@router.post("/query")
def query_ai(data: QueryRequest, db: Session = Depends(get_db)):
    result = answer_query(
        db,
        sport=data.sport,
        season=data.season,
        season_type=data.season_type,
        team_code=data.team,
        question=data.question,
    )
    return result
