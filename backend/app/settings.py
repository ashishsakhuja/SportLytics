from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://sportshub:sportshub@localhost:5432/sportshub"
    ENV: str = "local"

    # Semi-official NFL feeds (no API key)
    # Weekly schedule + score/status (XML)
    NFL_SCORESTRIP_URL: str = (
        "https://www.nfl.com/ajax/scorestrip?season={season}&seasonType={season_type}&week={week}"
    )

    # Optional: richer per-game details (JSON)
    NFL_GTD_URL: str = "https://static.nfl.com/liveupdate/game-center/{eid}/{eid}_gtd.json"


settings = Settings()
