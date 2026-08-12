# Munich semantic-clutter pilot

This pilot covers a 4 km by 4 km area centred on Marienplatz, Munich. It proves
the Bayern download, semantic overlay, MapInfo conversion, and Ellipse import
workflow at 2 m resolution before applying it to a city or Bundesland.

## Source data

- Bayern DGM1 supplies ground elevation.
- Bayern DOM1 supplies surface elevation. `max(DOM1 - DGM1, 0)` supplies AGL
  obstacle height only inside the semantic mask.
- Bayern LoD2 CityGML supplies building footprints.
- Bayern Basis-DLM WFS supplies `AX_Wald` and `AX_Gehoelz` polygons.
- `BRD20m_clutter.grc` supplies the background Ellipse clutter vocabulary.

The initial lookup resolves 25 DGM1 tiles, 25 DOM1 tiles, nine LoD2 CityGML
tiles, and one Basis-DLM response. Rerunning the builder reuses the saved cache;
it does not redownload files that are already complete.

## Build

From the repository root:

```powershell
$env:PYTHONPATH = "apps/api/src"
& ".venv/Scripts/python.exe" "scripts/build_munich_semantic_pilot.py"
```

Optional installation overrides:

- `MULTIPLANNER_ELLIPSE_GDAL_DIR`
- `MULTIPLANNER_BRD20_CLUTTER_PATH`
- `MULTIPLANNER_MAPINFO_PRO_DIR`

The MRR conversion uses the installed Precisely MapInfo Raster API rather than
GUI automation. `scripts/convert_mapinfo_mrr.ps1` calls the vendor-documented
`RasterProcessing.Convert` API with the `MI_MRR` driver.

## Output contract

The `semantic_clutter` cache directory contains separate, aligned Ellipse
inputs:

- `munich_pilot_buildings_2m.grc` contains only LoD2 building cells.
- `munich_pilot_trees_2m.grc` contains separate forest and woodland classes.
- `munich_pilot_agl_height_2m.mrr` is a continuous Float32 AGL-height raster in
  metres. It preserves actual height rather than a class label.
- `munich_pilot_brd_schema_clutter_2m_source.grd` plus
  `munich_pilot_brd20_clutter.class` remain available for creating the combined
  18-class BRD20-compatible semantic GRC.

The GeoTIFF and GRD files beside those deliverables are reproducible
intermediates and inspection copies. The pilot MRR is EPSG:32632, has 2 m cells,
and contains AGL values from 0 to approximately 95 m.

## Semantic class policy

The output retains the 18-class `BRD20m_clutter` vocabulary. Basis-DLM and LoD2
override the BRD20 background in this order:

- `AX_Wald` becomes class 7, `forest`.
- `AX_Gehoelz` becomes class 6, `sparse forest`.
- LoD2 building cells below 8 m become class 12, `urban`.
- LoD2 building cells from 8 m to below 25 m become class 13, `dense urban`.
- LoD2 building cells at or above 25 m become class 14, `high buildings`.

These building classes are categorical ranges, not exact heights. Exact forest
and building heights remain in the separate AGL MRR.

## Separate building and tree GRC files

The pilot builder uses the installed MapInfo Raster API to create the building
and tree GRC files directly. The building file classifies LoD2 footprint cells
as `building` and makes forest, woodland, and background cells null. The tree
file classifies `AX_Wald` as `forest`, `AX_Gehoelz` as `woodland`, and makes
building and background cells null.

This separation lets Ellipse load and enable buildings and trees independently.
Both files describe semantic presence; actual obstacle height remains in the
shared AGL MRR.

## Create the combined semantic GRC

MapInfo Raster is the validated GRC writer. In its Classify tool:

1. Open `munich_pilot_brd_schema_clutter_2m_source.grd`.
2. Select `Classified` output and `Discrete` intervals.
3. Load `munich_pilot_brd20_clutter.class`.
4. Save the result as `munich_pilot_brd_schema_clutter_2m.grc`.

The `.class` file is native MapInfo XML. Generic CSV interval files are not
equivalent and can trigger MapInfo parser errors.

## Configure Ellipse

Use the existing DTM MRR as the AMSL terrain source. Add either separate GRC or
the combined semantic GRC as clutter/ground-type layers without enabling
Height. Add
`munich_pilot_agl_height_2m.mrr` as the AGL layer, set its unit to metres, and
enable Height in GIS Data Sources.

Do not add DOM1 as another terrain layer. The correct profile relationship is:

```text
obstacle top AMSL = DTM ground AMSL + AGL height MRR
clutter meaning   = semantic GRC class
```

All three Ellipse layers must use the same UTM zone 32N project projection.

## Fixed pilot extent

- Centre: `48.1372, 11.5756`
- ETRS89 / UTM32 bounds: `689611,5332758` to `693611,5336758`

Basis-DLM uses Bayern's stored bounding-box query because the provider rejects
the equivalent direct WFS BBOX filter for this endpoint.
