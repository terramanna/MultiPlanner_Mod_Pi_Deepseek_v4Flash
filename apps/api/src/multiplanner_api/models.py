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


class PointProbeRequest(BaseModel):
    provider: str = "geobasis-nrw"
    dataset: Literal["dgm1", "dom1", "ndsm"] = "dgm1"
    lon: float
    lat: float


class PointProbeResponse(BaseModel):
    provider: str
    dataset: str
    lon: float
    lat: float
    height_m: float
    tile_id: str | None = None
    sampled_path: str


class TilePreviewRequest(BaseModel):
    provider: str = "geobasis-nrw"
    dataset: Literal["dgm1", "dom1", "ndsm"] = "dgm1"
    lon: float
    lat: float


class TilePreviewResponse(BaseModel):
    provider: str
    dataset: str
    tile_id: str | None = None
    image_path: str
    west: float
    south: float
    east: float
    north: float


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


class PolygonGeometryInput(BaseModel):
    kind: Literal["polygon"]
    coordinates: list[tuple[float, float]]


class CorridorGeometryInput(BaseModel):
    kind: Literal["corridor"]
    from_lon: float
    from_lat: float
    to_lon: float
    to_lat: float
    buffer_m: float = 150.0


class LocateSubsetRequest(BaseModel):
    provider: str = "lgln-ni"
    datasets: list[str] = ["dgm1", "dom1", "dop20"]
    geometry: PointGeometryInput | BboxGeometryInput | PolygonGeometryInput | CorridorGeometryInput


class TileSummary(BaseModel):
    provider: str
    dataset: str
    tile_id: str | None = None
    updated: str | None = None
    primary_url: str | None = None
    metadata: dict[str, str | None] = {}


class DatasetSubsetResult(BaseModel):
    provider: str | None = None
    dataset: str
    match_count: int
    tiles: list[TileSummary]
    estimated_source_bytes: int = 0
    estimated_ellipse_bytes: int = 0


class LocateSubsetResponse(BaseModel):
    provider: str
    geometry_kind: str
    results: list[DatasetSubsetResult]
    warnings: list[str] = []
    total_estimated_source_bytes: int = 0
    total_estimated_ellipse_bytes: int = 0


class DownloadSubsetRequest(LocateSubsetRequest):
    selection_name: str | None = None
    export_profile: str = "source_tiles"


class DownloadedFile(BaseModel):
    provider: str
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
    warnings: list[str] = []
    total_estimated_source_bytes: int = 0
    total_estimated_ellipse_bytes: int = 0


class MultiProbeRequest(BaseModel):
    provider: str = "geobasis-nrw"
    lon: float
    lat: float


class MultiProbeResponse(BaseModel):
    provider: str
    lon: float
    lat: float
    dgm_m: float | None = None
    dom_m: float | None = None
    ndsm_m: float | None = None
    dgm_error: str | None = None
    dom_error: str | None = None


class OpenFolderRequest(BaseModel):
    path: str
