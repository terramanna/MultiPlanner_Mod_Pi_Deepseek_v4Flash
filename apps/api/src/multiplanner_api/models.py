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
    link_name: str | None = None
    distance_m: float | None = None
    site_a_name: str | None = None
    site_a_label: str | None = None
    site_a_id: str | None = None
    site_a_type: str | None = None
    site_a_structure: str | None = None
    site_a_lon: float | None = None
    site_a_lat: float | None = None
    site_b_name: str | None = None
    site_b_label: str | None = None
    site_b_id: str | None = None
    site_b_type: str | None = None
    site_b_structure: str | None = None
    site_b_lon: float | None = None
    site_b_lat: float | None = None


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


class DownloadFailure(BaseModel):
    provider: str
    dataset: str
    tile_id: str | None = None
    source_url: str | None = None
    reason: str


class DownloadSubsetResponse(BaseModel):
    provider: str
    selection_name: str
    export_profile: str
    output_dir: str
    expected_file_count: int = 0
    file_count: int
    files: list[DownloadedFile]
    failed_downloads: list[DownloadFailure] = []
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


class ProfileEndpointInput(BaseModel):
    lon: float
    lat: float
    height_m: float = 0.0


class PathProfileRequest(BaseModel):
    provider: str = "auto"
    source: Literal["dgm1", "dom1", "dgm1_dom1"] = "dgm1_dom1"
    site_a: ProfileEndpointInput
    site_b: ProfileEndpointInput
    antenna_height_m: float = 30.0
    frequency_mhz: float = 6000.0
    fresnel_zone: int = 1
    sample_count: int = 33


class PathProfileSample(BaseModel):
    index: int
    ratio: float
    lon: float
    lat: float
    distance_m: float
    los_height_m: float
    fresnel_radius_m: float
    fresnel_lower_m: float
    dgm_m: float | None = None
    dom_m: float | None = None
    selected_height_m: float | None = None
    clearance_m: float | None = None
    error: str | None = None


class PathProfileResponse(BaseModel):
    provider: str
    source: str
    distance_m: float
    antenna_height_m: float
    frequency_mhz: float
    fresnel_zone: int
    samples: list[PathProfileSample]
    warnings: list[str] = []


class OpenFolderRequest(BaseModel):
    path: str
