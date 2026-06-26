import asyncio
import json
import os
import queue as queue_module
import subprocess
import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path

from multiplanner_api.config import load_settings
from multiplanner_api.downloads import download_subset
from multiplanner_api.models import (
    ConfigResponse,
    DownloadSubsetRequest,
    DownloadSubsetResponse,
    HealthResponse,
    LocateSubsetRequest,
    LocateSubsetResponse,
    OpenFolderRequest,
    SearchPlacesResponse,
)
from multiplanner_api.providers import SERVICE_PROVIDERS
from multiplanner_api.search import search_places
from multiplanner_api.subsets import locate_subsets

settings = load_settings()

app = FastAPI(
    title="MultiPlanner API",
    version="0.1.0",
    summary="Local-first terrain and LOS backend scaffold",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", service="multiplanner-api")


@app.get("/api/v1/config", response_model=ConfigResponse)
def read_config() -> ConfigResponse:
    return ConfigResponse(
        project_name=settings.project_name,
        provider_mode=settings.provider_mode,
        default_crs=settings.default_crs,
        cache_root=settings.cache_root,
    )


@app.get("/api/v1/search/places", response_model=SearchPlacesResponse)
def search_place_candidates(q: str) -> SearchPlacesResponse:
    try:
        return search_places(q)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/providers")
def list_providers() -> dict[str, object]:
    auto_datasets = sorted({dataset for config in SERVICE_PROVIDERS.values() for dataset in config["datasets"]})
    return {
        "providers": [
            {
                "name": "auto",
                "label": "Auto (split by provider)",
                "datasets": auto_datasets,
            },
            *[
            {
                "name": name,
                "label": config["label"],
                "datasets": sorted(config["datasets"].keys()),
            }
            for name, config in SERVICE_PROVIDERS.items()
            ],
        ]
    }


@app.post("/api/v1/subsets/locate", response_model=LocateSubsetResponse)
def locate_remote_subset(request: LocateSubsetRequest) -> LocateSubsetResponse:
    try:
        return locate_subsets(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/subsets/download", response_model=DownloadSubsetResponse)
def download_remote_subset(request: DownloadSubsetRequest) -> DownloadSubsetResponse:
    try:
        return download_subset(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/subsets/download-stream")
async def download_remote_subset_stream(request: DownloadSubsetRequest) -> StreamingResponse:
    q: queue_module.SimpleQueue = queue_module.SimpleQueue()

    def run_download() -> None:
        def emit(tile_id: str, current: int, total: int) -> None:
            q.put({"type": "progress", "tile_id": tile_id, "current": current, "total": total})
        try:
            result = download_subset(request, on_progress=emit)
            q.put({"type": "done", "result": result.model_dump()})
        except ValueError as exc:
            q.put({"type": "error", "message": str(exc)})
        except Exception as exc:
            q.put({"type": "error", "message": str(exc)})

    threading.Thread(target=run_download, daemon=True).start()

    async def generate():
        while True:
            try:
                event = q.get_nowait()
                yield f"data: {json.dumps(event)}\n\n"
                if event["type"] in ("done", "error"):
                    break
            except queue_module.Empty:
                await asyncio.sleep(0.1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/v1/subsets/file")
def read_downloaded_subset_file(path: str) -> FileResponse:
    cache_root = Path(settings.cache_root).resolve()
    candidate = Path(path).resolve()
    try:
        candidate.relative_to(cache_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="File is outside the cache root.") from exc

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found.")

    return FileResponse(candidate, filename=candidate.name)


@app.post("/api/v1/subsets/open-folder")
def open_downloaded_subset_folder(request: OpenFolderRequest) -> dict[str, str]:
    cache_root = Path(settings.cache_root).resolve()
    candidate = Path(request.path).resolve()
    try:
        candidate.relative_to(cache_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Folder is outside the cache root.") from exc

    if not candidate.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found.")

    try:
        if os.name == "nt":
            os.startfile(candidate)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(candidate)])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to open folder: {exc}") from exc

    return {"status": "opened", "path": str(candidate)}
