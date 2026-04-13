from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    allowed_mime_types: set[str] = Field(
        default_factory=lambda: {"image/jpeg", "image/png", "image/webp"}
    )
    max_upload_bytes: int = 2_000_000

    min_width: int = 600
    min_height: int = 600

    # Default required / target crop size: 2x2 inch @ 300 DPI -> 600x600 px
    target_width: int = 600
    target_height: int = 600
    aspect_tolerance: float = 0.02

    blur_laplacian_var_threshold: float = 120.0

    background_white_ratio_threshold: float = 0.70
    background_edge_ratio_threshold: float = 0.08

    temp_dir: Path = Field(default_factory=lambda: default_temp_dir())


def project_root() -> Path:
    # backend/app/config.py -> backend/app -> backend -> project root
    return Path(__file__).resolve().parents[2]


def default_temp_dir() -> Path:
    return project_root() / "tmp"


def get_settings() -> Settings:
    return Settings()

