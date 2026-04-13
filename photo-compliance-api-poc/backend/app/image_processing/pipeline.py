from __future__ import annotations

from PIL import Image

from app.config import Settings
from app.image_processing.compliance import run_compliance_checks
from app.image_processing.cropping import FaceDetection, crop_face_centered
from app.image_processing.utils import LowResolutionError, encode_image, load_pil_image

def _face_to_crop_coords(
    face: FaceDetection | None, crop_box: tuple[int, int, int, int]
) -> FaceDetection | None:
    if face is None:
        return None
    cx, cy, _, _ = crop_box
    return FaceDetection(x=face.x - cx, y=face.y - cy, w=face.w, h=face.h)


def process_upload_bytes(image_bytes: bytes, settings: Settings) -> tuple[Image.Image, Image.Image, bytes, tuple[int, int, int, int], list, list[str], bool]:
    original = load_pil_image(image_bytes)
    img_w, img_h = original.size
    if img_w < settings.min_width or img_h < settings.min_height:
        raise LowResolutionError("Low resolution ( minimum 600x600 required)")
    cropped, crop_box, face_in_original = crop_face_centered(original, settings)
    face_in_cropped = _face_to_crop_coords(face_in_original, crop_box)

    checks, warnings = run_compliance_checks(
        original_upload_bytes=len(image_bytes),
        cropped_pil=cropped,
        face_in_cropped=face_in_cropped,
        settings=settings,
    )
    overall_pass = all(c.passed or c.level == "warning" for c in checks)

    cropped_bytes = encode_image(cropped, fmt="JPEG", jpeg_quality=92)
    return original, cropped, cropped_bytes, crop_box, checks, warnings, overall_pass

