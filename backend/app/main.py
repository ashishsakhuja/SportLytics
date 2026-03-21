from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.settings import settings

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROUTER_IMPORT_ERRORS: list[dict] = []


def _safe_include(import_path: str, router_attr: str = "router") -> None:
    try:
        module = __import__(import_path, fromlist=[router_attr])
        router = getattr(module, router_attr)
        app.include_router(router)
        print(f"[startup] included router: {import_path}")
    except Exception as exc:
        error_payload = {
            "module": import_path,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        ROUTER_IMPORT_ERRORS.append(error_payload)
        print(f"[startup] FAILED router: {import_path} -> {type(exc).__name__}: {exc}")


@app.get("/healthz")
def healthz():
    return {
        "ok": len(ROUTER_IMPORT_ERRORS) == 0,
        "router_errors": ROUTER_IMPORT_ERRORS,
    }


_safe_include("app.routes.news")
_safe_include("app.routes.meta")
_safe_include("app.routes.feed")
_safe_include("app.routes.social")
_safe_include("app.routes.dashboards_nfl")
_safe_include("app.routes.nfl")
_safe_include("app.routes.analytics")
_safe_include("app.routes.analytics_sos")
_safe_include("app.routes.analytics_nfl_ingame")
_safe_include("app.routes.analytics_nba_ingame")
_safe_include("app.routes.analytics_nhl_ingame")
_safe_include("app.routes.ai")
_safe_include("app.routes.analytics_mlb_ingame")
_safe_include("app.routes.analytics_custom")
_safe_include("app.routes.analytics_advstats")
_safe_include("app.routes.community")
_safe_include("app.routes.auth")
_safe_include("app.routes.billing")