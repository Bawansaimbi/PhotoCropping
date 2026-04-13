const fileInput = document.getElementById("fileInput");
const processBtn = document.getElementById("processBtn");
const manualCropBtn = document.getElementById("manualCropBtn");
const downloadLink = document.getElementById("downloadLink");
const statusEl = document.getElementById("status");

const originalImg = document.getElementById("originalImg");
const croppedImg = document.getElementById("croppedImg");
const overlay = document.getElementById("overlay");
const checksEl = document.getElementById("checks");
const overallEl = document.getElementById("overall");
const warningsEl = document.getElementById("warnings");
const originalWrap = document.getElementById("originalWrap");

let currentFile = null;
let currentJobId = null;

let isDragging = false;
let dragStart = null; // {x,y} in canvas coords
let cropRect = null; // {x,y,w,h} in canvas coords

function setStatus(msg) {
  statusEl.textContent = msg || "";
}

function setDownload(jobId) {
  if (!jobId) {
    downloadLink.href = "#";
    downloadLink.setAttribute("aria-disabled", "true");
    return;
  }
  downloadLink.href = `/api/download/${encodeURIComponent(jobId)}`;
  downloadLink.removeAttribute("aria-disabled");
}

function badgeClass(result) {
  if (result === "ok") return "badge ok";
  if (result === "warn") return "badge warn";
  return "badge bad";
}

function renderResults(data) {
  overallEl.innerHTML = "";

  checksEl.innerHTML = "";
  for (const c of data.checks || []) {
    const cls = c.passed ? "ok" : c.level === "warning" ? "warn" : "bad";
    const msg = c.message || "";
    const li = document.createElement("li");
    li.className = "check";
    li.innerHTML = `
      <div class="meta">
        <div class="name">${escapeHtml(c.name)}</div>
        <div class="msg">${escapeHtml(msg)}</div>
      </div>
      <span class="${badgeClass(cls)}">${c.passed ? "PASS" : c.level.toUpperCase()}</span>
    `;
    checksEl.appendChild(li);
  }

  if ((data.warnings || []).length > 0) {
    warningsEl.textContent = `Warnings: ${data.warnings.join(" | ")}`;
  } else {
    warningsEl.textContent = "";
  }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function syncOverlaySize() {
  const rect = originalImg.getBoundingClientRect();
  if (!rect.width || !rect.height) return;

  // Canvas pixel size should match rendered size for correct pointer math
  overlay.width = Math.round(rect.width);
  overlay.height = Math.round(rect.height);
  redrawOverlay();
}

function redrawOverlay() {
  const ctx = overlay.getContext("2d");
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  if (!cropRect) return;

  ctx.fillStyle = "rgba(124, 92, 255, 0.12)";
  ctx.strokeStyle = "rgba(124, 92, 255, 0.9)";
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 4]);

  ctx.fillRect(cropRect.x, cropRect.y, cropRect.w, cropRect.h);
  ctx.strokeRect(cropRect.x, cropRect.y, cropRect.w, cropRect.h);
}

function getPointerPos(evt) {
  const r = overlay.getBoundingClientRect();
  const x = evt.clientX - r.left;
  const y = evt.clientY - r.top;
  return {
    x: Math.max(0, Math.min(overlay.width, x)),
    y: Math.max(0, Math.min(overlay.height, y)),
  };
}

function normalizeRect(a, b) {
  const x0 = Math.min(a.x, b.x);
  const y0 = Math.min(a.y, b.y);
  const x1 = Math.max(a.x, b.x);
  const y1 = Math.max(a.y, b.y);
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

function canvasRectToImagePixels(rect) {
  const natW = originalImg.naturalWidth;
  const natH = originalImg.naturalHeight;
  if (!natW || !natH || !overlay.width || !overlay.height) return null;

  const sx = natW / overlay.width;
  const sy = natH / overlay.height;

  return {
    x: Math.round(rect.x * sx),
    y: Math.round(rect.y * sy),
    width: Math.round(rect.w * sx),
    height: Math.round(rect.h * sy),
  };
}

// Convert an image-space crop box (pixels) to canvas coordinates
function imagePixelsToCanvasRect(box) {
  if (!box) return null;
  const natW = originalImg.naturalWidth;
  const natH = originalImg.naturalHeight;
  if (!natW || !natH || !overlay.width || !overlay.height) return null;

  const sx = overlay.width / natW;
  const sy = overlay.height / natH;

  return {
    x: box.x * sx,
    y: box.y * sy,
    w: box.width * sx,
    h: box.height * sy,
  };
}

// Compute a crop outline that corresponds to a 600x600 px region in the image (2x2 inch @ 300 DPI).
function getFixedCropSizeCanvas() {
  const natW = originalImg.naturalWidth;
  const natH = originalImg.naturalHeight;

  if (!natW || !natH) {
    return { w: 0, h: 0 };
  }

  const canvasW = overlay.width;
  const canvasH = overlay.height;

  if (!canvasW || !canvasH) {
    return { w: 0, h: 0 };
  }

  // Compute uniform scale used to fit image inside canvas
  const scale = Math.min(canvasW / natW, canvasH / natH);

  // Actual displayed image size inside canvas
  const displayW = natW * scale;
  const displayH = natH * scale;

  const pxSize = 600; // desired crop size in image pixels

  // Convert 600 image pixels → canvas pixels
  let sizeCanvas = pxSize * scale;

  // Clamp if image is smaller than 600px
  sizeCanvas = Math.min(sizeCanvas, displayW, displayH);

  return {
    w: sizeCanvas,
    h: sizeCanvas
  };
}

fileInput.addEventListener("change", () => {
  currentFile = fileInput.files?.[0] || null;
  currentJobId = null;
  setDownload(null);
  croppedImg.removeAttribute("src");
  overallEl.textContent = "";
  checksEl.innerHTML = "";
  warningsEl.textContent = "";

  cropRect = null;
  redrawOverlay();

  if (!currentFile) {
    originalImg.removeAttribute("src");
    processBtn.disabled = true;
    setStatus("");
    return;
  }

  processBtn.disabled = false;

  const url = URL.createObjectURL(currentFile);
  originalImg.src = url;
  originalImg.onload = () => {
    syncOverlaySize();
  };
  setStatus("Ready to process.");
});

processBtn.addEventListener("click", async () => {
  if (!currentFile) return;

  setStatus("Uploading and processing...");
  processBtn.disabled = true;
  setDownload(null);

  try {
    const fd = new FormData();
    fd.append("file", currentFile);

    const res = await fetch("/api/process-photo", { method: "POST", body: fd });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`API error (${res.status}): ${txt}`);
    }

    const data = await res.json();
    renderResults(data);

    // Only allow cropping/downloading if all compliance checks pass (errors only).
    if (!data.overall_pass) {
      currentJobId = null;
      cropRect = null;
      croppedImg.removeAttribute("src");
      setDownload(null);
      manualCropBtn.disabled = true;
      setStatus("Compliance failed. Please review the checks below.");
      return;
    }

    currentJobId = data.job_id;

    // Visualize the automatic 600x600 crop on the original image
    if (data.crop_box) {
      const r = imagePixelsToCanvasRect(data.crop_box);
      if (r) {
        cropRect = r;
        redrawOverlay();
      }
    }

    const bust = Date.now();
    croppedImg.src = `/api/download/${encodeURIComponent(currentJobId)}?t=${bust}`;
    setDownload(currentJobId);
    manualCropBtn.disabled = false;
    setStatus("Done.");
  } catch (e) {
    setStatus(String(e?.message || e));
  } finally {
    processBtn.disabled = !currentFile;
  }
});

manualCropBtn.addEventListener("click", async () => {
  if (!currentJobId) {
    setStatus("Process a photo first.");
    return;
  }
  if (!cropRect || cropRect.w < 8 || cropRect.h < 8) {
    setStatus("Draw a crop rectangle on the original image first.");
    return;
  }

  const px = canvasRectToImagePixels(cropRect);
  if (!px) {
    setStatus("Image not ready.");
    return;
  }

  setStatus("Applying manual crop...");
  manualCropBtn.disabled = true;

  try {
    const res = await fetch("/api/manual-crop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        x: px.x,
        y: px.y,
        width: px.width,
        height: px.height,
        new_job: true,
      }),
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`API error (${res.status}): ${txt}`);
    }

    const data = await res.json();
    currentJobId = data.job_id;
    renderResults(data);

    const bust = Date.now();
    croppedImg.src = `/api/download/${encodeURIComponent(currentJobId)}?t=${bust}`;
    setDownload(currentJobId);
    setStatus("Manual crop applied.");
  } catch (e) {
    setStatus(String(e?.message || e));
  } finally {
    manualCropBtn.disabled = false;
  }
});

overlay.addEventListener("pointerdown", (evt) => {
  if (!originalImg.src) return;
  overlay.setPointerCapture(evt.pointerId);
  isDragging = true;
  dragStart = getPointerPos(evt);
  const { w, h } = getFixedCropSizeCanvas();
  let x = dragStart.x - w / 2;
  let y = dragStart.y - h / 2;
  x = Math.max(0, Math.min(overlay.width - w, x));
  y = Math.max(0, Math.min(overlay.height - h, y));
  cropRect = { x, y, w, h };
  redrawOverlay();
});

overlay.addEventListener("pointermove", (evt) => {
  if (!isDragging || !dragStart) return;
  const cur = getPointerPos(evt);
  const { w, h } = getFixedCropSizeCanvas();
  let x = cur.x - w / 2;
  let y = cur.y - h / 2;
  x = Math.max(0, Math.min(overlay.width - w, x));
  y = Math.max(0, Math.min(overlay.height - h, y));
  cropRect = { x, y, w, h };
  redrawOverlay();
});

overlay.addEventListener("pointerup", () => {
  isDragging = false;
  dragStart = null;
});

new ResizeObserver(() => syncOverlaySize()).observe(originalWrap);
window.addEventListener("resize", () => syncOverlaySize());

