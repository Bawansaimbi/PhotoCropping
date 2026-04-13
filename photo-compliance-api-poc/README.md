# Photo Compliance API (POC)

Small FastAPI service + static web UI that:

- Accepts an uploaded image
- Does a deterministic face-centered crop (Haar cascade)
- Runs rule-based compliance checks
- Lets you manually re-crop and download the result

## Project layout

- `backend/app/main.py`: FastAPI app (serves UI + API)
- `backend/app/api/routes.py`: `/api/*` endpoints
- `backend/app/image_processing/`: decoding, cropping, checks
- `backend/app/storage.py`: temp on-disk storage keyed by `job_id`
- `frontend/`: static UI (`index.html`, `styles.css`, `app.js`)
- `tests/`: unit + API tests
- `scripts/generate_sample_images.py`: generate sample images into `sample_images/`

## Setup

Requires **Python 3.10+**.

From `photo-compliance-api-poc/`:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

Run Uvicorn from the `backend/` folder so `app.*` imports work:

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Open:

- UI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

## API quickstart

- `POST /api/process-photo` (multipart form-data `file`)
- `POST /api/manual-crop` (JSON body with `job_id` and crop rectangle)
- `GET /api/download/{job_id}` (streams `cropped.jpg`)

## Tests

From `photo-compliance-api-poc/`:

```bash
pytest -q
```

## Sample images

Generate demo images (not committed to git):

```bash
python scripts/generate_sample_images.py
```

## Notes / limitations

- Face detection uses a simple Haar cascade; it can fail on extreme angles/lighting.
- Background “white/busy” checks are heuristics (HSV whiteness + edge density), not full segmentation/object detection.
- Temp storage is local on disk (`backend/tmp/{job_id}/...`) and not auto-cleaned in this POC.

