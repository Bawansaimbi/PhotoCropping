from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router


def project_root() -> Path:
    # backend/app/main.py -> backend/app -> backend -> project root
    return Path(__file__).resolve().parents[2]


def create_app() -> FastAPI:
    app = FastAPI(title="Photo Compliance API (POC)")
    app.include_router(api_router)

    frontend_dir = project_root() / "frontend"
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        index_path = frontend_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"ok": True, "message": "Frontend not built yet. Use /docs for the API."}

    return app


app = create_app()

