## Architecture

- **FastAPI** serves:
  - Static UI at `/` and `/static/*`
  - API under `/api/*`
- **Image pipeline** (OpenCV + Pillow):
  - Decode bytes → orientation fix (EXIF) → RGB
  - Face detect (Haar cascade) → compute deterministic crop rectangle
  - Crop → run compliance checks → encode cropped image (JPEG)
- **Storage**:
  - Local disk temp store keyed by `job_id`
  - Files under `backend/tmp/{job_id}/original.bin` and `backend/tmp/{job_id}/cropped.jpg`

```mermaid
flowchart TD
  user[User] --> ui[Web UI /]
  ui -->|multipart upload| api1[POST /api/process-photo]
  api1 --> pipeline[Decode → detect → crop → checks]
  pipeline --> store[Save original + cropped to tmp]
  store --> resp[JSON response + job_id]
  resp --> ui
  ui --> api2[POST /api/manual-crop]
  ui --> api3[GET /api/download/{job_id}]
```

## Endpoints

### `POST /api/process-photo`

- **Input**: multipart `file`
- **Optional query params**: `target_width`, `target_height`, `min_width`, `min_height`, `aspect_tolerance`
- **Output**: JSON including:
  - `job_id`
  - `crop_box` (x/y/width/height)
  - `checks[]` (per-rule status)
  - `overall_pass` (warnings don’t fail overall)
  - `warnings[]`

### `POST /api/manual-crop`

- **Input**: JSON body:
  - `job_id`, `x`, `y`, `width`, `height`, `new_job`
- **Behavior**:
  - Loads the stored original bytes
  - Crops using the provided rectangle (clamped to image bounds)
  - Re-runs compliance checks on the manually cropped result
  - Stores a new job by default (`new_job=true`)

### `GET /api/download/{job_id}`

- Streams `cropped.jpg` for the given job.

## Cropping strategy (deterministic)

1. Detect the **largest** face bounding box using Haar cascade.
2. Center crop around the face center with a small upward bias.
3. Expand the crop to match target aspect ratio, and enforce minimum dimensions.
4. Clamp crop rectangle to the image bounds.
5. If no face is detected, fallback to a deterministic center crop that matches target aspect ratio.

## Compliance checks (POC rules)

All thresholds are in `backend/app/config.py` (`Settings`).

- **File size**: uploaded bytes <= `max_upload_bytes`
- **Minimum resolution**: cropped width/height >= `min_width` / `min_height`
- **Aspect ratio**: \(|(w/h) - target| <= aspect_tolerance\)
- **Blur** (warning): variance of Laplacian (grayscale) >= `blur_laplacian_var_threshold`
- **Background whiteness** (warning): ratio of background pixels with low saturation + high value in HSV >= `background_white_ratio_threshold`
- **Background busy/objects heuristic** (warning): edge density in background (Canny) <= `background_edge_ratio_threshold`

## Known limitations

- Haar cascades are fast but not robust vs. modern detectors; some faces won’t be detected.
- Background checks are heuristics and are sensitive to lighting and camera exposure.
- Temp storage is not cleaned automatically in this POC.

