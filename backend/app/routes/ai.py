from fastapi import APIRouter
from pydantic import BaseModel
from app.services.ai_service import generate_chart_caption

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
    caption = generate_chart_caption(
        chart_id=data.chart_id,
        summary=data.summary,
    )

    return {"caption": caption}