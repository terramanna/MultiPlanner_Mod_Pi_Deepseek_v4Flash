from pydantic import BaseModel
from typing import Literal


class HealthResponse(BaseModel):
    status: str
    service: str


class ConfigResponse(BaseModel):
    project_name: str
    provider_mode: str
    default_crs: str
    cache_root: str


class SearchCandidate(BaseModel):
    label: str
    lon: float
    lat: float
    source: str


class SearchPlacesResponse(BaseModel):
    query: str
    candidates: list[SearchCandidate]


class PointGeometryInput(BaseModel):
    kind: Literal["point"]
    lon: float
    lat: float


class BboxGeometryInput(BaseModel):
    kind: Literal["bbox"]
    west: float
    south: float
    east: float
    north: float


class CorridorGeometryInput(BaseModel):
    kind: Literal["corridor"]
    from_lon: float
    from_lat: float
    to_lon: float
    to_lat: float
    buffer_m: float = 50.0


class LocateSubsetRequest(BaseModel):
    provider: str = "lgln-ni"
    datasets: list[str] = ["dgm1", "dom1", "dop20"]
    geometry: PointGeometryInput | BboxGeometryInput | CorridorGeometryInput


class TileSummary(BaseModel):
    provider: str
    dataset: str
    tile_id: str | None = None
    updated: str | None = None
    primary_url: str | None = None
    metadata: dict[str, str | None] = {}


class DatasetSubsetResult(BaseModel):
    dataset: str
    match_count: int
    tiles: list[TileSummary]


class LocateSubsetResponse(BaseModel):
    provider: str
    geometry_kind: str
    results: list[DatasetSubsetResult]


class DownloadSubsetRequest(LocateSubsetRequest):
    selection_name: str | None = None
    export_profile: str = "source_tiles"


class DownloadedFile(BaseModel):
    dataset: str
    tile_id: str | None = None
    source_url: str
    saved_path: str


class DownloadSubsetResponse(BaseModel):
    provider: str
    selection_name: str
    export_profile: str
    output_dir: str
    file_count: int
    files: list[DownloadedFile]
    exports: list[str] = []
