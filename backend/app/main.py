from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes.news import router as news_router
from .routes.meta import router as meta_router
from .routes.feed import router as feed_router
from app.routes.social import router as social_router
from app.routes.dashboards_nfl import router as dashboards_nfl_router
from app.routes.nfl import router as nfl_router
from app.routes.analytics import router as analytics_router

app = FastAPI(title="SportsHub API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://10.0.0.219:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(news_router)
app.include_router(meta_router)
app.include_router(feed_router)
app.include_router(social_router)
app.include_router(dashboards_nfl_router)
app.include_router(nfl_router)
app.include_router(analytics_router)


