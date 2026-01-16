from fastapi import FastAPI
from .routes.news import router as news_router
from .routes.meta import router as meta_router
from .routes.feed import router as feed_router
from app.routes.social import router as social_router


app = FastAPI(title="SportsHub API")
app.include_router(news_router)
app.include_router(meta_router)
app.include_router(feed_router)
app.include_router(social_router)