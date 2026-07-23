from __future__ import annotations

from pathlib import Path

import numpy as np
from shapely.geometry import shape

from multiplanner_api.semantic_clutter import (
    BRD20_CLASSES,
    agl_height_grid,
    brd20_clutter_grid,
    dlm_vegetation_features,
    lod2_building_features,
    write_mapinfo_class_profile,
)


def test_mapinfo_profile_uses_native_class_xml(tmp_path: Path) -> None:
    profile = tmp_path / "brd20.class"

    write_mapinfo_class_profile(profile)

    text = profile.read_text(encoding="utf-8")
    assert "<ClassifiedIntervalStoreType" in text
    assert text.count("<IntervalLine>") == len(BRD20_CLASSES)
    assert "<NewClassName>forest</NewClassName>" in text
    assert "<LowerLimit>18</LowerLimit>" in text


def test_agl_height_grid_uses_dom_minus_dgm_inside_semantic_mask() -> None:
    dgm = np.array([[500.0, 500.0], [500.0, 500.0]], dtype=np.float32)
    dom = np.array([[512.5, 510.0], [498.0, np.nan]], dtype=np.float32)
    mask = np.array([[1, 0], [85, 43]], dtype=np.uint8)

    height = agl_height_grid(dgm, dom, mask)

    np.testing.assert_array_equal(height, [[12.5, 0.0], [0.0, 0.0]])


def test_brd20_grid_overlays_vegetation_and_building_height_classes() -> None:
    base = np.full((2, 3), 5, dtype=np.uint8)
    height = np.array([[20, 20, 20], [7.9, 8, 25]], dtype=np.float32)
    mask = np.array([[0, 1, 43], [85, 85, 85]], dtype=np.uint8)

    clutter = brd20_clutter_grid(base, height, mask)

    np.testing.assert_array_equal(clutter, [[5, 7, 6], [12, 13, 14]])


def test_dlm_vegetation_features_extracts_wald_and_gehoelz(tmp_path: Path) -> None:
    source = tmp_path / "basis.gml"
    source.write_text(_basis_dlm_xml(), encoding="utf-8")

    features = dlm_vegetation_features(source)

    assert [feature["properties"]["family"] for feature in features] == ["forest", "woodland"]
    assert [round(shape(feature["geometry"]).area) for feature in features] == [100, 100]


def test_lod2_building_features_project_citygml_surfaces(tmp_path: Path) -> None:
    source = tmp_path / "lod2.gml"
    source.write_text(_lod2_xml(), encoding="utf-8")

    features = lod2_building_features([source])

    assert len(features) == 1
    assert features[0]["properties"]["family"] == "building"
    assert round(shape(features[0]["geometry"]).area) == 100


def _basis_dlm_xml() -> str:
    return """<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:adv="adv">
  <wfs:member><adv:AX_Wald><adv:position><gml:Polygon>
    <gml:exterior><gml:LinearRing><gml:posList srsDimension="2">0 0 10 0 10 10 0 10 0 0</gml:posList></gml:LinearRing></gml:exterior>
  </gml:Polygon></adv:position></adv:AX_Wald></wfs:member>
  <wfs:member><adv:AX_Gehoelz><adv:position><gml:Polygon>
    <gml:exterior><gml:LinearRing><gml:posList srsDimension="2">20 0 30 0 30 10 20 10 20 0</gml:posList></gml:LinearRing></gml:exterior>
  </gml:Polygon></adv:position></adv:AX_Gehoelz></wfs:member>
</wfs:FeatureCollection>"""


def _lod2_xml() -> str:
    return """<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0" xmlns:bldg="http://www.opengis.net/citygml/building/2.0" xmlns:gml="http://www.opengis.net/gml">
  <core:cityObjectMember><bldg:Building><bldg:boundedBy><bldg:GroundSurface><bldg:lod2MultiSurface><gml:MultiSurface>
    <gml:surfaceMember><gml:Polygon><gml:exterior><gml:LinearRing>
      <gml:posList srsDimension="3">0 0 5 10 0 5 10 10 5 0 10 5 0 0 5</gml:posList>
    </gml:LinearRing></gml:exterior></gml:Polygon></gml:surfaceMember>
  </gml:MultiSurface></bldg:lod2MultiSurface></bldg:GroundSurface></bldg:boundedBy></bldg:Building></core:cityObjectMember>
</core:CityModel>"""
