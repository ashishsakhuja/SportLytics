from fastapi import FastAPI
from .routes.news import router as news_router
from .routes.meta import router as meta_router


app = FastAPI(title="SportsHub API")
app.include_router(news_router)
app.include_router(meta_router)
