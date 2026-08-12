from pathlib import Path
from types import SimpleNamespace

from multiplanner_api import raster_tiles


def test_dom_hillshade_is_a_supported_raster_tile_dataset() -> None:
    raster_tiles._validate_request("geobasis-nrw", "dom1hs", 12, 2100, 1400)


def test_dom_hillshade_fetches_dom_source_tiles(monkeypatch, tmp_path: Path) -> None:
    requests = []
    downloads = []
    tile = SimpleNamespace(tile_id="dom-tile")

    def locate(request):
        requests.append(request)
        return SimpleNamespace(results=[SimpleNamespace(tiles=[tile])])

    def download(provider, dataset, requested_tile):
        downloads.append((provider, dataset, requested_tile))
        return [tmp_path / "dom.tif"]

    monkeypatch.setattr(raster_tiles, "locate_subsets", locate)
    monkeypatch.setattr(raster_tiles, "_download_tile_sources", download)

    paths = raster_tiles._source_paths("geobasis-nrw", "dom1hs", 12, 2100, 1400)

    assert requests[0].datasets == ["dom1"]
    assert downloads == [("geobasis-nrw", "dom1", tile)]
    assert paths == [tmp_path / "dom.tif"]


def test_dom_hillshade_uses_hillshade_renderer(monkeypatch, tmp_path: Path) -> None:
    calls = []
    source = tmp_path / "dom-warped.tif"
    target = tmp_path / "dom-hillshade.png"
    monkeypatch.setattr(raster_tiles, "_render_hillshade_png", lambda *args: calls.append(args))
    monkeypatch.setattr(
        raster_tiles,
        "_render_grayscale_png",
        lambda *_args: raise_unexpected_grayscale(),
    )

    raster_tiles._render_dataset_png(source, target, "dom1hs")

    assert calls == [(source, target)]


def raise_unexpected_grayscale() -> None:
    raise AssertionError("DOM hillshade must not use the grayscale renderer")
