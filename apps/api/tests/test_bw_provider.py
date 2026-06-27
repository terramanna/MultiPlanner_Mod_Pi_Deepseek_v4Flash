import json

import pytest
from shapely.geometry import box

from multiplanner_api.bw import _tile_cells, _tile_record, locate_tiles, summarize_tiles
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

STUTTGART_POINT = "9.1829,48.7758"


def test_lgl_bw_provider_lists_terrain_surface_ortho_and_building_datasets() -> None:
    assert provider_dataset_names("lgl-bw") == ("dgm1", "dom1", "dop20", "bdom")


def test_tile_cells_single_point_returns_one_cell() -> None:
    pt = box(513_500, 5_402_500, 513_500, 5_402_500)
    cells = _tile_cells(pt)
    assert cells == [(513, 5402)]


def test_tile_cells_straddles_boundary_returns_four_cells() -> None:
    area = box(514_999, 5_403_999, 515_001, 5_404_001)
    cells = _tile_cells(area)
    assert set(cells) == {
        (513, 5402),
        (513, 5404),
        (515, 5402),
        (515, 5404),
    }


def test_tile_record_url_format() -> None:
    record = _tile_record("dgm1", 513, 5402)
    assert record["tile_id"] == "bw_dgm1_513_5402"
    assert record["primary_url"] == "https://opengeodata.lgl-bw.de/data/dgm/dgm1_32_513_5402_2_bw.zip"


@pytest.mark.parametrize(
    ("dataset", "expected_url"),
    [
        ("dom1", "https://opengeodata.lgl-bw.de/data/dom1/dom1_32_513_5402_2_bw.zip"),
        ("dop20", "https://opengeodata.lgl-bw.de/data/dop20/dop20rgb_32_513_5402_2_bw.zip"),
        ("bdom", "https://opengeodata.lgl-bw.de/data/lod2/LoD2_32_513_5402_2_bw.zip"),
    ],
)
def test_tile_record_supports_dom_ortho_and_lod2(dataset: str, expected_url: str) -> None:
    record = _tile_record(dataset, 513, 5402)
    assert record["tile_id"] == f"bw_{dataset}_513_5402"
    assert record["primary_url"] == expected_url


def test_locate_tiles_point_geometry_returns_one_tile() -> None:
    config = SERVICE_PROVIDERS["lgl-bw"]["datasets"]["dgm1"]
    tiles = locate_tiles(
        "dgm1",
        config=config,
        geometry=STUTTGART_POINT,
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert tiles == [
        {
            "tile_id": "bw_dgm1_513_5402",
            "primary_url": "https://opengeodata.lgl-bw.de/data/dgm/dgm1_32_513_5402_2_bw.zip",
        }
    ]


@pytest.mark.parametrize(
    ("dataset", "expected_url"),
    [
        ("dom1", "https://opengeodata.lgl-bw.de/data/dom1/dom1_32_513_5402_2_bw.zip"),
        ("dop20", "https://opengeodata.lgl-bw.de/data/dop20/dop20rgb_32_513_5402_2_bw.zip"),
        ("bdom", "https://opengeodata.lgl-bw.de/data/lod2/LoD2_32_513_5402_2_bw.zip"),
    ],
)
def test_locate_tiles_point_geometry_supports_dom_ortho_and_lod2(dataset: str, expected_url: str) -> None:
    config = SERVICE_PROVIDERS["lgl-bw"]["datasets"][dataset]
    tiles = locate_tiles(
        dataset,
        config=config,
        geometry=STUTTGART_POINT,
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert tiles == [{"tile_id": f"bw_{dataset}_513_5402", "primary_url": expected_url}]


def test_locate_tiles_envelope_geometry() -> None:
    geom = json.dumps({
        "xmin": 9.15, "ymin": 48.76, "xmax": 9.21, "ymax": 48.81,
        "spatialReference": {"wkid": 4326},
    })
    config = SERVICE_PROVIDERS["lgl-bw"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=geom,
                         geometry_type="esriGeometryEnvelope", timeout=1)
    assert len(tiles) >= 1
    for tile in tiles:
        assert tile["primary_url"].startswith("https://opengeodata.lgl-bw.de/data/dgm/dgm1_32_")
        assert tile["primary_url"].endswith("_2_bw.zip")


def test_locate_tiles_polygon_geometry() -> None:
    geom = json.dumps({"rings": [[[9.15, 48.76], [9.21, 48.76],
                                   [9.21, 48.81], [9.15, 48.81], [9.15, 48.76]]]})
    config = SERVICE_PROVIDERS["lgl-bw"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=geom,
                         geometry_type="esriGeometryPolygon", timeout=1)
    assert len(tiles) >= 1


def test_summarize_tiles_has_correct_provider_and_dataset() -> None:
    config = SERVICE_PROVIDERS["lgl-bw"]["datasets"]["dgm1"]
    summaries = summarize_tiles("dgm1", config=config, geometry=STUTTGART_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary["provider"] == "lgl-bw"
    assert summary["dataset"] == "dgm1"
    assert summary["tile_id"] == "bw_dgm1_513_5402"
    assert "lgl-bw.de" in summary["source"]


@pytest.mark.parametrize("dataset", ["dom1", "dop20", "bdom"])
def test_summarize_tiles_supports_dom_ortho_and_lod2(dataset: str) -> None:
    config = SERVICE_PROVIDERS["lgl-bw"]["datasets"][dataset]
    summaries = summarize_tiles(dataset, config=config, geometry=STUTTGART_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    assert summaries[0]["provider"] == "lgl-bw"
    assert summaries[0]["dataset"] == dataset
    assert summaries[0]["tile_id"] == f"bw_{dataset}_513_5402"
    assert "lgl-bw.de" in summaries[0]["source"]


def test_locate_tiles_raises_for_oversized_area() -> None:
    geom = json.dumps({
        "xmin": 7.2, "ymin": 47.5, "xmax": 10.5, "ymax": 49.9,
        "spatialReference": {"wkid": 4326},
    })
    config = SERVICE_PROVIDERS["lgl-bw"]["datasets"]["dgm1"]
    with pytest.raises(ValueError, match="200 tiles"):
        locate_tiles("dgm1", config=config, geometry=geom,
                     geometry_type="esriGeometryEnvelope", timeout=1)
