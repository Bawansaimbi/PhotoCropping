from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from app.config import Settings
from app.image_processing.utils import clamp_box_to_image, pil_to_bgr, safe_crop


@dataclass(frozen=True)
class FaceDetection:
    x: int
    y: int
    w: int
    h: int


def detect_largest_face(pil_img: Image.Image) -> FaceDetection | None:
    bgr = pil_to_bgr(pil_img)
    return _detect_largest_face(bgr)


def _detect_largest_face(bgr: np.ndarray) -> FaceDetection | None:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        flags=cv2.CASCADE_SCALE_IMAGE,
        minSize=(60, 60),
    )
    if faces is None or len(faces) == 0:
        return None

    x, y, w, h = max(faces, key=lambda f: int(f[2]) * int(f[3]))
    return FaceDetection(int(x), int(y), int(w), int(h))


def _center_crop_box(img_w: int, img_h: int, target_ratio: float) -> tuple[int, int, int, int]:
    img_ratio = img_w / img_h if img_h else 1.0
    if img_ratio >= target_ratio:
        # too wide -> limit width
        h = img_h
        w = int(round(h * target_ratio))
    else:
        w = img_w
        h = int(round(w / target_ratio))

    x = int(round((img_w - w) / 2))
    y = int(round((img_h - h) / 2))
    return clamp_box_to_image(x, y, w, h, img_w, img_h)


def compute_face_centered_crop_box(
    img_w: int,
    img_h: int,
    face: FaceDetection | None,
    settings: Settings,
) -> tuple[tuple[int, int, int, int], FaceDetection | None]:
    # Fixed-size square crop: 2x2 inch @ 300 DPI -> 600x600 px.
    # Use the configured target/min dimensions but never exceed the image bounds.
    side_px = min(
        settings.target_width,
        settings.target_height,
        settings.min_width,
        img_w,
        img_h,
    )

    # Fallback: no face detected -> centered square crop.
    if face is None:
        w = h = int(side_px)
        x = int(round((img_w - w) / 2))
        y = int(round((img_h - h) / 2))
        x, y, w, h = clamp_box_to_image(x, y, w, h, img_w, img_h)
        return (x, y, w, h), None

    # Face detected: fixed-size square centered on face with slight upward bias.
    cx = face.x + face.w / 2
    cy = face.y + face.h * 0.45

    w = h = int(side_px)
    x = int(round(cx - w / 2))
    y = int(round(cy - h / 2))
    x, y, w, h = clamp_box_to_image(x, y, w, h, img_w, img_h)
    return (x, y, w, h), face


def crop_face_centered(pil_img: Image.Image, settings: Settings) -> tuple[Image.Image, tuple[int, int, int, int], FaceDetection | None]:
    img_w, img_h = pil_img.size
    bgr = pil_to_bgr(pil_img)
    face = _detect_largest_face(bgr)
    crop_box, face_used = compute_face_centered_crop_box(img_w, img_h, face, settings)
    x, y, w, h = crop_box
    cropped = safe_crop(pil_img, x, y, w, h)
    return cropped, crop_box, face_used

