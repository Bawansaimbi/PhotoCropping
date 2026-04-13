from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sample_images"
OUT.mkdir(parents=True, exist_ok=True)


def make_face_like(img: Image.Image) -> Image.Image:
    d = ImageDraw.Draw(img)
    w, h = img.size
    cx, cy = w // 2, h // 2
    r = min(w, h) // 6
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(30, 30, 30), width=10)
    d.ellipse([cx - r // 2, cy - r // 2, cx - r // 6, cy - r // 6], fill=(30, 30, 30))
    d.ellipse([cx + r // 6, cy - r // 2, cx + r // 2, cy - r // 6], fill=(30, 30, 30))
    d.arc([cx - r // 2, cy - r // 10, cx + r // 2, cy + r // 2], start=20, end=160, fill=(30, 30, 30), width=8)
    return img


def save_jpg(img: Image.Image, name: str, quality: int = 92) -> None:
    img.save(OUT / name, format="JPEG", quality=quality, optimize=True)


def main() -> None:
    # valid: white background, sharp
    valid = Image.new("RGB", (900, 900), (255, 255, 255))
    make_face_like(valid)
    save_jpg(valid, "valid.jpg")

    # blurry: same but blurred
    blurry = valid.filter(ImageFilter.GaussianBlur(radius=4))
    save_jpg(blurry, "blurry.jpg")

    # low_resolution: too small
    low = Image.new("RGB", (320, 320), (255, 255, 255))
    make_face_like(low)
    save_jpg(low, "low_resolution.jpg")

    # wrong_aspect: rectangular
    wrong = Image.new("RGB", (1000, 650), (255, 255, 255))
    make_face_like(wrong)
    save_jpg(wrong, "wrong_aspect.jpg")

    # busy_background: noisy background
    rng = np.random.default_rng(0)
    noise = rng.integers(0, 255, size=(900, 900, 3), dtype=np.uint8)
    busy = Image.fromarray(noise, mode="RGB")
    make_face_like(busy)
    save_jpg(busy, "busy_background.jpg")

    print(f"Wrote samples to: {OUT}")


if __name__ == "__main__":
    main()

