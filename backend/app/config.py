"""
Central settings object. EVERY env var the app needs is declared here, with
a sane default where one exists. Nothing else in the codebase should call
os.environ / os.getenv directly — always import `settings` from here.

This file is intentionally complete in the boilerplate (not a TODO stub) —
it's pure declaration, no business logic, and every other module depends
on it existing correctly.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "AI Sales Agent"
    app_env: str = "development"
    app_debug: bool = True
    business_id: str | None = None

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sales_agent"
    alembic_database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/sales_agent"

    # --- LLM ---
    llm_provider: str = "groq"
    llm_fallback_enabled: bool = True
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    google_api_key: str | None = None
    google_model: str = "gemini-1.5-pro"

    # --- Embeddings ---
    embedding_provider: str = "google"
    embedding_model: str = "text-embedding-004"
    embedding_dimensions: int = 768

    # --- Conversation ---
    max_history_messages: int = 20

    # --- WhatsApp ---
    meta_app_secret: str | None = None
    meta_verify_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_access_token: str | None = None

    # --- Instagram ---
    instagram_page_access_token: str | None = None
    instagram_page_id: str | None = None

    # --- Facebook ---
    facebook_page_access_token: str | None = None
    facebook_page_id: str | None = None

    # --- Rate limiting ---
    webhook_rate_limit_per_minute: int = 60
    llm_rate_limit_per_conversation_per_minute: int = 10

    # --- CORS ---
    cors_origins: str = "http://localhost:5173"

    # --- Auth ---
    jwt_secret: str = "change-me-to-a-random-64-char-string"
    jwt_expire_minutes: int = 1440

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
