from functools import cached_property

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "GhostWriter AI"
    database_url: str = Field(..., alias="DATABASE_URL")
    secret_key: str = Field(..., alias="SECRET_KEY")
    jwt_secret_key: str = Field(..., alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    social_analyzer_path: str = "../social_analyzer"
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_host: str | None = Field(default=None, alias="OLLAMA_HOST")
    ollama_model: str = Field(default="gemma3:4b", alias="OLLAMA_MODEL")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.1-8b-instant", alias="GROQ_MODEL")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-1.5-flash", alias="GEMINI_MODEL")
    unsplash_access_key: str | None = Field(default=None, alias="UNSPLASH_ACCESS_KEY")
    pexels_api_key: str | None = Field(default=None, alias="PEXELS_API_KEY")
    visual_provider: str = Field(default="unsplash", alias="VISUAL_PROVIDER")
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_api_base_url: str = Field(default="https://api.telegram.org", alias="TELEGRAM_API_BASE_URL")
    telegram_dry_run: bool = Field(default=True, alias="TELEGRAM_DRY_RUN")
    debug_chat: bool = Field(default=False, alias="DEBUG_CHAT")

    @cached_property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "")

    @cached_property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
