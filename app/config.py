from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    app_name: str = "Tender Documentation Summarizer"
    app_version: str = "2.0.0"
    debug: bool = False

    max_file_size_mb: int = Field(default=20, ge=1, le=100)
    max_text_chars: int = Field(default=500_000, ge=10_000)
    chunk_size: int = Field(default=12_000, ge=1_000)
    chunk_overlap: int = Field(default=1_000, ge=0)

    llm_provider: str = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_timeout_seconds: int = Field(default=120, ge=10, le=600)

    enable_ocr: bool = True
    ocr_language: str = "rus+eng"
    ocr_dpi: int = Field(default=200, ge=100, le=400)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""
    return Settings()
