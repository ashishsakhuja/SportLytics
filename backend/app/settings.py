from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://sportshub:sportshub@localhost:5432/sportshub"
    ENV: str = "local"
    NFL_SCORESTRIP_URL: str = (
        "https://static.nfl.com/ajax/scorestrip?season={season}&seasonType={season_type}&week={week}")
    NFL_SCORESTRIP_LIVE_URL: str = "https://static.nfl.com/liveupdate/scorestrip/ss.xml"
    ESPN_NFL_SCOREBOARD_URL: str = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    ESPN_NFL_SUMMARY_URL: str = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
    # Optional: richer per-game details (JSON)
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


settings = Settings()