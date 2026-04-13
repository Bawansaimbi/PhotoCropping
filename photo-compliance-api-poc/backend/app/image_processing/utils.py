from __future__ import annotations

from io import BytesIO
from typing import Literal

import numpy as np
from PIL import Image, ImageOps


class ImageDecodeError(ValueError):
    pass


class LowResolutionError(ValueError):
    pass


def load_pil_image(image_bytes: bytes) -> Image.Image:
    try:
        with Image.open(BytesIO(image_bytes)) as im:
            im = ImageOps.exif_transpose(im)
            return im.convert("RGB")
    except Exception as e:  # noqa: BLE001
        raise ImageDecodeError("Could not decode image bytes") from e


def pil_to_bgr(pil_img: Image.Image) -> np.ndarray:
    rgb = np.array(pil_img, dtype=np.uint8)
    # RGB -> BGR
    return rgb[:, :, ::-1].copy()


def bgr_to_pil(bgr: np.ndarray) -> Image.Image:
    rgb = bgr[:, :, ::-1]
    return Image.fromarray(rgb.astype(np.uint8), mode="RGB")


def encode_image(
    pil_img: Image.Image,
    fmt: Literal["JPEG", "PNG"] = "JPEG",
    jpeg_quality: int = 92,
) -> bytes:
    buf = BytesIO()
    if fmt == "JPEG":
        pil_img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    else:
        pil_img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def clamp_int(v: float, lo: int, hi: int) -> int:
    return int(max(lo, min(hi, round(v))))


def clamp_box_to_image(
    x: int, y: int, w: int, h: int, img_w: int, img_h: int
) -> tuple[int, int, int, int]:
    w = max(1, min(w, img_w))
    h = max(1, min(h, img_h))
    x = max(0, min(x, img_w - w))
    y = max(0, min(y, img_h - h))
    return x, y, w, h


def safe_crop(pil_img: Image.Image, x: int, y: int, w: int, h: int) -> Image.Image:
    img_w, img_h = pil_img.size
    x, y, w, h = clamp_box_to_image(x, y, w, h, img_w, img_h)
    return pil_img.crop((x, y, x + w, y + h))

