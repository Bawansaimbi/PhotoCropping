from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.config import get_settings
from app.image_processing.compliance import run_compliance_checks
from app.image_processing.cropping import detect_largest_face
from app.image_processing.pipeline import process_upload_bytes
from app.image_processing.utils import (
    LowResolutionError,
    clamp_box_to_image,
    encode_image,
    load_pil_image,
    safe_crop,
)
from app.models import ManualCropRequest, ProcessResponse
from app.storage import TempStorage

router = APIRouter(prefix="/api", tags=["api"])


@router.post("/process-photo", response_model=ProcessResponse)
async def process_photo(
    file: UploadFile,
    target_width: int | None = Query(default=None, ge=1),
    target_height: int | None = Query(default=None, ge=1),
    min_width: int | None = Query(default=None, ge=1),
    min_height: int | None = Query(default=None, ge=1),
    aspect_tolerance: float | None = Query(default=None, gt=0.0),
) -> ProcessResponse:
    settings = get_settings()
    if target_width is not None:
        settings.target_width = target_width
    if target_height is not None:
        settings.target_height = target_height
    if min_width is not None:
        settings.min_width = min_width
    if min_height is not None:
        settings.min_height = min_height
    if aspect_tolerance is not None:
        settings.aspect_tolerance = aspect_tolerance

    if file.content_type not in settings.allowed_mime_types:
        raise HTTPException(status_code=415, detail="Unsupported file type.")

    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large.")

    try:
        original, cropped, cropped_bytes, crop_box, checks, warnings, overall_pass = (
            process_upload_bytes(data, settings)
        )
    except LowResolutionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Failed to process image: {e}") from e

    storage = TempStorage(settings)
    job_id = storage.new_job_id()
    storage.save_original(job_id, data)
    storage.save_cropped_jpeg(job_id, cropped_bytes)

    x, y, w, h = crop_box
    return ProcessResponse(
        overall_pass=overall_pass,
        checks=checks,
        crop_box={"x": x, "y": y, "width": w, "height": h},
        job_id=job_id,
        warnings=warnings,
    )


@router.post("/manual-crop", response_model=ProcessResponse)
async def manual_crop(req: ManualCropRequest) -> ProcessResponse:
    settings = get_settings()
    storage = TempStorage(settings)

    if not storage.has_job(req.job_id):
        raise HTTPException(status_code=404, detail="job_id not found or expired.")

    original_bytes = storage.get_original_bytes(req.job_id)
    original = load_pil_image(original_bytes)

    if req.width <= 0 or req.height <= 0:
        raise HTTPException(status_code=422, detail="width/height must be positive.")

    img_w, img_h = original.size

    # Always use a fixed square crop size (2x2 inch @ 300 DPI -> 600x600 px),
    # centered on the user-drawn rectangle.
    side_px = min(
        settings.target_width,
        settings.target_height,
        settings.min_width,
        img_w,
        img_h,
    )
    cx = req.x + req.width / 2
    cy = req.y + req.height / 2
    x = int(round(cx - side_px / 2))
    y = int(round(cy - side_px / 2))
    x, y, w, h = clamp_box_to_image(x, y, int(side_px), int(side_px), img_w, img_h)
    cropped = safe_crop(original, x, y, w, h)
    face = detect_largest_face(cropped)
    checks, warnings = run_compliance_checks(
        original_upload_bytes=len(original_bytes),
        cropped_pil=cropped,
        face_in_cropped=face,
        settings=settings,
    )
    overall_pass = all(c.passed or c.level == "warning" for c in checks)
    cropped_bytes = encode_image(cropped, fmt="JPEG", jpeg_quality=92)

    if req.new_job:
        job_id = storage.new_job_id()
        storage.save_original(job_id, original_bytes)
    else:
        job_id = req.job_id
    storage.save_cropped_jpeg(job_id, cropped_bytes)

    return ProcessResponse(
        overall_pass=overall_pass,
        checks=checks,
        crop_box={"x": x, "y": y, "width": w, "height": h},
        job_id=job_id,
        warnings=warnings,
    )


@router.get("/download/{job_id}")
async def download(job_id: str):
    settings = get_settings()
    storage = TempStorage(settings)

    p = storage.get_cropped_path(job_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="job_id not found or expired.")

    return FileResponse(str(p), media_type="image/jpeg", filename="cropped.jpg")

