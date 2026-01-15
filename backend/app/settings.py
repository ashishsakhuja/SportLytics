from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://sportshub:sportshub@localhost:5432/sportshub"
    ENV: str = "local"

settings = Settings()
