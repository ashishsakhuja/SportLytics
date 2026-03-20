from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user_required
from app.db import get_db
from app.models import UserAccount
from app.services.ai_insights_service import answer_query, build_storylines
from app.services.ai_service import generate_chart_answer_cached, generate_chart_caption_cached

router = APIRouter(prefix="/ai", tags=["AI"])


class ChatTurn(BaseModel):
    role: str
    text: str = Field(..., min_length=1)


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
    session_id: str | None = None
    history: list[ChatTurn] = []


class ChartQueryRequest(BaseModel):
    chart_id: str
    chart_title: str
    sport: str
    season: int
    season_type: str
    team: str | None = None
    summary: dict
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


@router.post("/chart-query")
def chart_query(data: ChartQueryRequest):
    answer = generate_chart_answer_cached(
        chart_id=data.chart_id,
        chart_title=data.chart_title,
        sport=data.sport,
        season=data.season,
        season_type=data.season_type,
        team=data.team,
        summary=data.summary,
        question=data.question,
    )
    return {"answer": answer}


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
def query_ai(
    data: QueryRequest,
    current_user: UserAccount = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    result = answer_query(
        db,
        sport=data.sport,
        season=data.season,
        season_type=data.season_type,
        team_code=data.team,
        question=data.question,
        session_id=data.session_id,
        conversation_history=[{"role": item.role, "text": item.text} for item in (data.history or [])],
    )
    return {
        **result,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "display_name": current_user.display_name,
        },
    }
