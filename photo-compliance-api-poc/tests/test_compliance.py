from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw

from app.config import Settings
from app.image_processing.compliance import (
    check_aspect_ratio,
    check_background,
    check_blur,
    check_resolution,
)


def _png_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_resolution_and_aspect_pass_for_square_image():
    s = Settings()
    img = Image.new("RGB", (600, 600), color=(255, 255, 255))
    w, h = img.size

    r = check_resolution(w, h, s)
    a = check_aspect_ratio(w, h, s)

    assert r.passed is True
    assert a.passed is True


def test_blur_check_flags_blurry_image():
    s = Settings()

    img = Image.new("RGB", (700, 700), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([120, 120, 580, 580], outline=(0, 0, 0), width=8)
    sharp = img

    # Make it blurry via downscale/upscale (stable across PIL versions)
    blurry = sharp.resize((200, 200), resample=Image.Resampling.BILINEAR).resize(
        (700, 700), resample=Image.Resampling.BILINEAR
    )

    sharp_res = check_blur(sharp, s)
    blurry_res = check_blur(blurry, s)

    assert sharp_res.passed is True
    assert blurry_res.passed is False
    assert blurry_res.level == "warning"


def test_background_whiteness_passes_for_white_background():
    s = Settings()
    img = Image.new("RGB", (650, 650), color=(255, 255, 255))

    checks = check_background(img, face=None, settings=s)
    names = {c.name: c for c in checks}

    assert names["background_white"].passed is True
    assert names["background_busy"].passed is True


def test_background_busy_flags_high_edge_density():
    s = Settings()
    rng = np.random.default_rng(0)
    noise = (rng.integers(0, 255, size=(650, 650, 3), dtype=np.uint8)).astype(np.uint8)
    img = Image.fromarray(noise, mode="RGB")

    checks = check_background(img, face=None, settings=s)
    busy = [c for c in checks if c.name == "background_busy"][0]

    assert busy.passed is False
    assert busy.level == "warning"

