from fastapi import APIRouter
from pydantic import BaseModel
from app.services.ai_service import generate_chart_caption_cached

router = APIRouter(prefix="/ai", tags=["AI"])


class ChartCaptionRequest(BaseModel):
    chart_id: str
    sport: str
    season: int
    season_type: str
    team: str
    summary: dict


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