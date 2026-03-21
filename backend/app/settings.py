from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "SportLytics API"
    ENV: str = "local"
    DATABASE_URL: str = "postgresql+psycopg2://sportlytics:sportlytics@127.0.0.1:5432/sportlytics"

    FRONTEND_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    SESSION_COOKIE_NAME: str = "sportlytics_session"
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: str = "lax"
    SESSION_COOKIE_DOMAIN: str | None = None
    SESSION_COOKIE_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 30

    NFL_SCORESTRIP_URL: str = (
        "https://static.nfl.com/ajax/scorestrip?season={season}&seasonType={season_type}&week={week}"
    )
    NFL_SCORESTRIP_LIVE_URL: str = "https://static.nfl.com/liveupdate/scorestrip/ss.xml"
    ESPN_NFL_SCOREBOARD_URL: str = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    ESPN_NFL_SUMMARY_URL: str = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
    NFL_GTD_URL: str = "https://static.nfl.com/liveupdate/game-center/{eid}/{eid}_gtd.json"

    ESPN_NBA_SCOREBOARD_URL: str = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    ESPN_NBA_SUMMARY_URL: str = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
    ESPN_NBA_TEAMS_URL: str = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"

    ESPN_MLB_SCOREBOARD_URL: str = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
    ESPN_MLB_SUMMARY_URL: str = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary"
    ESPN_MLB_TEAMS_URL: str = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/teams"

    ESPN_NHL_SCOREBOARD_URL: str = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"
    ESPN_NHL_SUMMARY_URL: str = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary"
    ESPN_NHL_TEAMS_URL: str = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/teams"

    @field_validator("FRONTEND_ORIGINS", mode="before")
    @classmethod
    def _normalize_frontend_origins(cls, value: str | list[str] | None) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return ",".join(str(item).strip() for item in value if str(item).strip())
        return str(value).strip()

    @field_validator("SESSION_COOKIE_SAMESITE")
    @classmethod
    def _validate_samesite(cls, value: str) -> str:
        normalized = (value or "lax").strip().lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("SESSION_COOKIE_SAMESITE must be one of: lax, strict, none")
        return normalized

    @property
    def frontend_origins_list(self) -> list[str]:
        raw = (self.FRONTEND_ORIGINS or "").strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]


settings = Settings()