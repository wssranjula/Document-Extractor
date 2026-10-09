from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://verifier:verifier@localhost:5432/verifier"
    jwt_secret: str = "dev-only-change-this-jwt-secret-key"
    jwt_expire_minutes: int = 60 * 24
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "formulary-check"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    upload_dir: Path = BACKEND_ROOT / "data" / "uploads"
    seed_email: str = "reviewer@example.com"
    seed_password: str = "Reviewer123!"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"


settings = Settings()
