from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import create_app


def _png_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_process_then_download_then_manual_crop_flow():
    app = create_app()
    client = TestClient(app)

    img = Image.new("RGB", (900, 700), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.ellipse([320, 180, 560, 420], outline=(0, 0, 0), width=8)  # face-ish
    payload = _png_bytes(img)

    r = client.post(
        "/api/process-photo",
        files={"file": ("test.png", payload, "image/png")},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "job_id" in data
    assert "checks" in data

    job_id = data["job_id"]
    dl = client.get(f"/api/download/{job_id}")
    assert dl.status_code == 200
    assert dl.headers.get("content-type", "").startswith("image/jpeg")
    assert len(dl.content) > 1000

    r2 = client.post(
        "/api/manual-crop",
        json={
            "job_id": job_id,
            "x": 150,
            "y": 80,
            "width": 500,
            "height": 500,
            "new_job": True,
        },
    )
    assert r2.status_code == 200, r2.text
    data2 = r2.json()
    assert data2["job_id"] != job_id

    dl2 = client.get(f"/api/download/{data2['job_id']}")
    assert dl2.status_code == 200
    assert len(dl2.content) > 1000

