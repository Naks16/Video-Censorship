"""
Application configuration — loads from .env file.
All settings have sane defaults so the system works with minimal config.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── API Keys ──────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    youtube_api_key: str = ""

    # ── Model Configuration ───────────────────────────────────────────────────
    # whisper model size: tiny | base | small | medium | large
    whisper_model: str = "base"

    # HuggingFace CLIP model
    clip_model: str = "openai/clip-vit-base-patch32"

    # OpenAI chat model
    openai_model: str = "gpt-4o"

    # ── Processing Config ─────────────────────────────────────────────────────
    temp_dir: Path = Path("./temp")

    # Maximum frames to sample from trailer for vision analysis
    max_frames: int = 30

    # Interval between sampled frames in seconds
    frame_interval_seconds: float = 1.0


    # ── Server Config ─────────────────────────────────────────────────────────
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    host: str = "0.0.0.0"
    port: int = 8000

    # ── Computed Properties ───────────────────────────────────────────────────
    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_youtube_api(self) -> bool:
        return bool(self.youtube_api_key)

    @field_validator("temp_dir", mode="before")
    @classmethod
    def ensure_temp_dir(cls, v: str | Path) -> Path:
        p = Path(v)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
