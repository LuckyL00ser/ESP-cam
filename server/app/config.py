from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    captures_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "captures"
    )
    database_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "esp_cam.db"
    )
    upload_field_name: str = "image"
    max_upload_bytes: int = 5 * 1024 * 1024
    capture_retention_minutes: int = 60
    capture_cleanup_interval_seconds: int = 60
    detector_url: str = ""
    stats_timeseries_default_limit: int = 100
    stats_classes_default_limit: int = 50

    @property
    def detector_url_normalized(self) -> str:
        return self.detector_url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.captures_dir.mkdir(parents=True, exist_ok=True)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
