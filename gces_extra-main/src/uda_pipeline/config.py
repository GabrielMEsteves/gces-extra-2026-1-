from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="UDA_")

    db_path: Path = Field(default=Path("data/uda.db"))
    storage_dir: Path = Field(default=Path("data/storage"))
    sources_file: Path = Field(default=Path("config/sources.json"))
    poll_interval_seconds: int = Field(default=86400, ge=60)
    llm_provider: str = Field(default="mock")
    llm_model: str = Field(default="gpt-4.1-mini")
    llm_api_key: str | None = Field(default=None)
    llm_base_url: str = Field(default="https://api.openai.com/v1")
    max_full_scan_chars: int = Field(default=18000, ge=1000)
    max_llm_retries: int = Field(default=1, ge=0, le=3)
    enable_ocr_fallback: bool = Field(default=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings
