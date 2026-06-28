from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    project_name: str
    provider_mode: str
    default_crs: str
    cache_root: str
    output_dir: str
    cors_origins: tuple[str, ...]
    ellipse_gdal_dir: str
    geocoder_url: str
    geocoder_countrycodes: str
    geocoder_email: str
    network_db_path: str


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
