from dataclasses import dataclass
import os
from pathlib import Path

# apps/api/src/multiplanner_api/config.py -> repo root is four levels up.
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_env_file(path: Path) -> None:
    """Populate os.environ from a local, untracked KEY=VALUE file.

    Lets each machine (server, laptop, ...) keep its own MULTIPLANNER_*
    paths in a gitignored .env instead of requiring identical paths or
    a system environment variable set before every launch. Real
    environment variables always win over the file.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_env_file(_REPO_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    project_name: str
    provider_mode: str
    default_crs: str
    cache_root: str
    source_cache_max_bytes: int
    tile_cache_max_bytes: int
    output_dir: str
    cors_origins: tuple[str, ...]
    ellipse_gdal_dir: str
    geocoder_url: str
    geocoder_countrycodes: str
    geocoder_email: str
    network_db_path: str


def _parse_cache_gb(env_var: str, default_gb: float) -> int:
    try:
        gb = float(os.getenv(env_var, str(default_gb)))
    except ValueError:
        gb = default_gb
    return max(0, int(gb * 1024 ** 3))


def load_settings() -> Settings:
    cors_origins = tuple(
        origin.strip()
        for origin in os.getenv(
            "MULTIPLANNER_CORS_ORIGIN",
            "http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:5175,http://127.0.0.1:5186",
        ).split(",")
        if origin.strip()
    )
    return Settings(
        project_name=os.getenv("MULTIPLANNER_PROJECT_NAME", "MultiPlanner"),
        provider_mode=os.getenv("MULTIPLANNER_PROVIDER_MODE", "public-open-data"),
        default_crs=os.getenv("MULTIPLANNER_DEFAULT_CRS", "EPSG:4326"),
        cache_root=os.getenv("MULTIPLANNER_CACHE_ROOT", "./data/cache"),
        source_cache_max_bytes=_parse_cache_gb("MULTIPLANNER_SOURCE_CACHE_MAX_GB", 20.0),
        tile_cache_max_bytes=_parse_cache_gb("MULTIPLANNER_TILE_CACHE_MAX_GB", 5.0),
        output_dir=os.getenv("MULTIPLANNER_OUTPUT_DIR", ""),
        cors_origins=cors_origins,
        ellipse_gdal_dir=os.getenv(
            "MULTIPLANNER_ELLIPSE_GDAL_DIR",
            r"C:\Program Files\InfoVista\Ellipse 9\gdal",
        ),
        geocoder_url=os.getenv(
            "MULTIPLANNER_GEOCODER_URL",
            "https://nominatim.openstreetmap.org/search",
        ),
        geocoder_countrycodes=os.getenv("MULTIPLANNER_GEOCODER_COUNTRYCODES", "de"),
        geocoder_email=os.getenv("MULTIPLANNER_GEOCODER_EMAIL", ""),
        network_db_path=os.getenv("MULTIPLANNER_NETWORK_DB_PATH", ""),
    )
