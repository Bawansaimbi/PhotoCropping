from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CropBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class CheckResult(BaseModel):
    name: str
    passed: bool
    value: Any | None = None
    expected: Any | None = None
    message: str | None = None
    level: Literal["info", "warning", "error"] = "info"


class ProcessResponse(BaseModel):
    overall_pass: bool
    checks: list[CheckResult]
    crop_box: CropBox
    job_id: str
    warnings: list[str] = Field(default_factory=list)


class ManualCropRequest(BaseModel):
    job_id: str
    x: int
    y: int
    width: int
    height: int
    new_job: bool = True

