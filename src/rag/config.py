from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    database_url: str = "postgresql+asyncpg://rag:rag@localhost:5432/ragforge"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()