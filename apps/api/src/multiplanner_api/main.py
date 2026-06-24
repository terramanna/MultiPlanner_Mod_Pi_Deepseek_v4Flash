from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from multiplanner_api.config import load_settings
from multiplanner_api.downloads import download_subset
from multiplanner_api.models import (
    ConfigResponse,
    DownloadSubsetRequest,
    DownloadSubsetResponse,
    HealthResponse,
    LocateSubsetRequest,
    LocateSubsetResponse,
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
    return {
        "providers": [
            {
                "name": name,
                "label": config["label"],
                "datasets": sorted(config["datasets"].keys()),
            }
            for name, config in SERVICE_PROVIDERS.items()
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
