from __future__ import annotations

from dataclasses import dataclass
from math import dist

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import FaceLandmarkerOptions, FaceLandmarker, RunningMode

from app.config import Settings
from app.image_processing.cropping import FaceDetection
from app.models import CheckResult


_face_landmarker_options = FaceLandmarkerOptions(
    base_options=mp_python.BaseOptions(model_asset_path=None),
    running_mode=RunningMode.IMAGE,
    num_faces=1,
    min_face_detection_confidence=0.5,
    min_face_presence_confidence=0.5,
    output_face_blendshapes=False,
    output_facial_transformation_matrixes=False,
)

# Lazy initialiser – created on first use to avoid import-time model download issues.
_FACE_LANDMARKER: FaceLandmarker | None = None


def _get_face_landmarker() -> FaceLandmarker:
    global _FACE_LANDMARKER
    if _FACE_LANDMARKER is None:
        import urllib.request, pathlib, os, tempfile
        model_dir = pathlib.Path(tempfile.gettempdir()) / "mediapipe_models"
        model_dir.mkdir(exist_ok=True)
        model_path = model_dir / "face_landmarker.task"
        if not model_path.exists():
            url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
            urllib.request.urlretrieve(url, model_path)
        opts = FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        _FACE_LANDMARKER = FaceLandmarker.create_from_options(opts)
    return _FACE_LANDMARKER


@dataclass(frozen=True)
class BackgroundMetrics:
    white_ratio: float
    edge_ratio: float


def check_resolution(img_w: int, img_h: int, settings: Settings, *, name: str = "min_resolution") -> CheckResult:
    passed = img_w >= settings.min_width and img_h >= settings.min_height
    return CheckResult(
        name=name,
        passed=passed,
        value={"width": img_w, "height": img_h},
        expected={"min_width": settings.min_width, "min_height": settings.min_height},
        message=None if passed else "Image resolution is below the minimum requirement.",
        level="error" if not passed else "info",
    )


def check_face_present(face: FaceDetection | None, *, name: str = "human_face_present") -> CheckResult:
    passed = face is not None
    return CheckResult(
        name=name,
        passed=passed,
        value={"detected": bool(face)},
        expected={"detected": True},
        message=None if passed else "No human face detected in the cropped image.",
        level="error" if not passed else "info",
    )


def check_aspect_ratio(img_w: int, img_h: int, settings: Settings, *, name: str = "aspect_ratio") -> CheckResult:
    target = settings.target_width / settings.target_height
    ratio = img_w / img_h if img_h else 0.0
    passed = abs(ratio - target) <= settings.aspect_tolerance
    return CheckResult(
        name=name,
        passed=passed,
        value={"ratio": ratio, "width": img_w, "height": img_h},
        expected={"target_ratio": target, "tolerance": settings.aspect_tolerance},
        message=None if passed else "Image aspect ratio is outside the allowed tolerance.",
        level="error" if not passed else "info",
    )


def check_blur(pil_img: Image.Image, settings: Settings, *, name: str = "blur") -> CheckResult:
    rgb = np.array(pil_img, dtype=np.uint8)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    var = float(lap.var())
    passed = var >= settings.blur_laplacian_var_threshold
    return CheckResult(
        name=name,
        passed=passed,
        value={"laplacian_var": var},
        expected={"min_laplacian_var": settings.blur_laplacian_var_threshold},
        message=None if passed else "Image appears blurry (low edge detail).",
        level="warning" if not passed else "info",
    )


def _eye_aspect_ratio(landmarks: list, idxs: list[int]) -> float:
    p = [landmarks[i] for i in idxs]
    # Standard EAR: (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
    num = dist((p[1].x, p[1].y), (p[5].x, p[5].y)) + dist(
        (p[2].x, p[2].y), (p[4].x, p[4].y)
    )
    den = 2.0 * dist((p[0].x, p[0].y), (p[3].x, p[3].y))
    if den <= 0:
        return 0.0
    return num / den


def check_eyes_open(
    pil_img: Image.Image,
    face: FaceDetection | None,  # unused but kept for API symmetry
    *,
    name: str = "eyes_open",
) -> CheckResult:
    rgb = np.array(pil_img.convert("RGB"), dtype=np.uint8)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    try:
        landmarker = _get_face_landmarker()
        results = landmarker.detect(mp_image)
    except Exception:
        return CheckResult(
            name=name,
            passed=False,
            value={"ear_left": 0.0, "ear_right": 0.0},
            expected={"ear_threshold": 0.21},
            message="Face landmark model unavailable; could not evaluate eyes.",
            level="error",
        )

    if not results.face_landmarks:
        return CheckResult(
            name=name,
            passed=False,
            value={"ear_left": 0.0, "ear_right": 0.0},
            expected={"ear_threshold": 0.21},
            message="No face landmarks detected to evaluate eyes.",
            level="error",
        )

    face_landmarks = results.face_landmarks[0]

    # Indices for left/right eyes from MediaPipe FaceMesh topology.
    left_idxs = [33, 160, 158, 133, 153, 144]
    right_idxs = [362, 385, 387, 263, 373, 380]

    ear_left = _eye_aspect_ratio(face_landmarks, left_idxs)
    ear_right = _eye_aspect_ratio(face_landmarks, right_idxs)
    ear_threshold = 0.21

    passed = ear_left >= ear_threshold and ear_right >= ear_threshold

    return CheckResult(
        name=name,
        passed=passed,
        value={"ear_left": ear_left, "ear_right": ear_right},
        expected={"ear_threshold": ear_threshold},
        message=None
        if passed
        else "Eyes appear to be closed or heavily occluded.",
        level="error" if not passed else "info",
    )


def check_file_size(upload_bytes: int, settings: Settings, *, name: str = "file_size") -> CheckResult:
    passed = upload_bytes <= settings.max_upload_bytes
    return CheckResult(
        name=name,
        passed=passed,
        value={"upload_bytes": upload_bytes},
        expected={"max_upload_bytes": settings.max_upload_bytes},
        message=None if passed else "Upload exceeds maximum allowed file size.",
        level="error" if not passed else "info",
    )


def _background_mask(
    img_w: int, img_h: int, face: FaceDetection | None
) -> np.ndarray:
    mask = np.ones((img_h, img_w), dtype=np.uint8) * 255
    if face is None:
        return mask

    # Exclude an expanded face region from background sampling.
    pad_x = int(round(face.w * 0.30))
    pad_y = int(round(face.h * 0.40))
    x0 = max(0, face.x - pad_x)
    y0 = max(0, face.y - pad_y)
    x1 = min(img_w, face.x + face.w + pad_x)
    y1 = min(img_h, face.y + face.h + pad_y)
    mask[y0:y1, x0:x1] = 0
    return mask


def compute_background_metrics(pil_img: Image.Image, face: FaceDetection | None) -> BackgroundMetrics:
    rgb = np.array(pil_img, dtype=np.uint8)
    img_h, img_w = rgb.shape[:2]
    mask = _background_mask(img_w, img_h, face)

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]

    # White-ish: low saturation, high value.
    whiteish = (s <= 35) & (v >= 210) & (mask > 0)
    bg_pixels = int((mask > 0).sum())
    white_pixels = int(whiteish.sum())
    white_ratio = (white_pixels / bg_pixels) if bg_pixels else 0.0

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, threshold1=80, threshold2=160)
    edge_pixels = int(((edges > 0) & (mask > 0)).sum())
    edge_ratio = (edge_pixels / bg_pixels) if bg_pixels else 0.0

    return BackgroundMetrics(white_ratio=white_ratio, edge_ratio=edge_ratio)


def check_background(
    pil_img: Image.Image,
    face: FaceDetection | None,
    settings: Settings,
) -> list[CheckResult]:
    m = compute_background_metrics(pil_img, face)

    white_pass = m.white_ratio >= settings.background_white_ratio_threshold
    texture_pass = m.edge_ratio <= settings.background_edge_ratio_threshold

    white_check = CheckResult(
        name="background_white",
        passed=white_pass,
        value={"white_ratio": m.white_ratio},
        expected={"min_white_ratio": settings.background_white_ratio_threshold},
        message=None if white_pass else "Background may be too dark or colorful (not white enough).",
        level="warning" if not white_pass else "info",
    )

    # Temporarily disable background_busy check
    # texture_check = CheckResult(
    #     name="background_busy",
    #     passed=texture_pass,
    #     value={"edge_ratio": m.edge_ratio},
    #     expected={"max_edge_ratio": settings.background_edge_ratio_threshold},
    #     message=None if texture_pass else "Background may contain texture/objects (high edge density).",
    #     level="warning" if not texture_pass else "info",
    # )


    return [white_check]


def run_compliance_checks(
    *,
    original_upload_bytes: int,
    cropped_pil: Image.Image,
    face_in_cropped: FaceDetection | None,
    settings: Settings,
) -> tuple[list[CheckResult], list[str]]:
    w, h = cropped_pil.size
    checks: list[CheckResult] = []
    warnings: list[str] = []

    checks.append(check_file_size(original_upload_bytes, settings))
    checks.append(check_resolution(w, h, settings))
    checks.append(check_aspect_ratio(w, h, settings))
    checks.append(check_blur(cropped_pil, settings))
    checks.append(check_face_present(face_in_cropped))
    checks.append(check_eyes_open(cropped_pil, face_in_cropped))

    bg_checks = check_background(cropped_pil, face_in_cropped, settings)
    checks.extend(bg_checks)

    for c in checks:
        if not c.passed and c.level == "warning" and c.message:
            warnings.append(c.message)

    return checks, warnings


