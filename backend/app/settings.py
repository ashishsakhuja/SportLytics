from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://sportshub:sportshub@localhost:5432/sportshub"
    ENV: str = "local"

    # Semi-official NFL feeds (no API key)
    # Weekly schedule + score/status (XML)
    # Semi-official NFL feeds (no API key)
    NFL_SCORESTRIP_URL: str = (
        "https://static.nfl.com/ajax/scorestrip?season={season}&seasonType={season_type}&week={week}"
    )

    # Fallback: live “current week” scoreboard feed
    NFL_SCORESTRIP_LIVE_URL: str = "https://static.nfl.com/liveupdate/scorestrip/ss.xml"
    # ESPN public JSON (fallback / primary if NFL domains blocked)
    ESPN_NFL_SCOREBOARD_URL: str = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

    # Optional: richer per-game details (JSON)
    NFL_GTD_URL: str = "https://static.nfl.com/liveupdate/game-center/{eid}/{eid}_gtd.json"


settings = Settings()
