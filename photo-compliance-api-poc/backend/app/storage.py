from __future__ import annotations

import uuid
from pathlib import Path

from app.config import Settings


class TempStorage:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_dir = settings.temp_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def new_job_id(self) -> str:
        return uuid.uuid4().hex

    def _job_dir(self, job_id: str) -> Path:
        return self.base_dir / job_id

    def save_original(self, job_id: str, image_bytes: bytes) -> Path:
        d = self._job_dir(job_id)
        d.mkdir(parents=True, exist_ok=True)
        p = d / "original.bin"
        p.write_bytes(image_bytes)
        return p

    def save_cropped_jpeg(self, job_id: str, jpeg_bytes: bytes) -> Path:
        d = self._job_dir(job_id)
        d.mkdir(parents=True, exist_ok=True)
        p = d / "cropped.jpg"
        p.write_bytes(jpeg_bytes)
        return p

    def get_original_bytes(self, job_id: str) -> bytes:
        p = self._job_dir(job_id) / "original.bin"
        return p.read_bytes()

    def get_cropped_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "cropped.jpg"

    def has_job(self, job_id: str) -> bool:
        d = self._job_dir(job_id)
        return d.exists() and (d / "cropped.jpg").exists()

