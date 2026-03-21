from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.ai import router as ai_router
from app.routes.analytics import router as analytics_router
from app.routes.analytics_advstats import router as analytics_advstats_router
from app.routes.analytics_custom import router as analytics_custom_router
from app.routes.analytics_mlb_ingame import router as analytics_mlb_ingame_router
from app.routes.analytics_nba_ingame import router as analytics_nba_ingame_router
from app.routes.analytics_nfl_ingame import router as analytics_nfl_ingame_router
from app.routes.analytics_nhl_ingame import router as analytics_nhl_ingame_router
from app.routes.analytics_sos import router as analytics_sos_router
from app.routes.auth import router as auth_router
from app.routes.billing import router as billing_router
from app.routes.community import router as community_router
from app.routes.dashboards_nfl import router as dashboards_nfl_router
from app.routes.feed import router as feed_router
from app.routes.meta import router as meta_router
from app.routes.news import router as news_router
from app.routes.nfl import router as nfl_router
from app.routes.social import router as social_router
from app.settings import settings

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(news_router)
app.include_router(meta_router)
app.include_router(feed_router)
app.include_router(social_router)
app.include_router(dashboards_nfl_router)
app.include_router(nfl_router)
app.include_router(analytics_router)
app.include_router(analytics_sos_router)
app.include_router(analytics_nfl_ingame_router)
app.include_router(analytics_nba_ingame_router)
app.include_router(analytics_nhl_ingame_router)
app.include_router(ai_router)
app.include_router(analytics_mlb_ingame_router)
app.include_router(analytics_custom_router)
app.include_router(analytics_advstats_router)
app.include_router(community_router)
app.include_router(auth_router)
app.include_router(billing_router)
