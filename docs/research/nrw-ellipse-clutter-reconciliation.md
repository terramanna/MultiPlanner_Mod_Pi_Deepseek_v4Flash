# NRW Ellipse Clutter Reconciliation

This note captures what NRW official geodata can and cannot tell us when an
Ellipse path profile shows clutter and we need to reconcile whether the
obstruction is a building, vegetation, or a broader land-cover category.

Reviewed against the live NRW source catalogs on 2026-06-28.

## Summary

- `DOM1` is usable for obstruction-aware profile heights, not clutter identity.
- `DGM1` is usable as the bare-earth baseline.
- `LoD2` is the correct NRW source for building identity.
- `Basis-DLM` is the closest NRW source for broad non-building clutter classes.
- `nDOM50` is useful for relative object height, not object type.
- `bDOM50` is not a building-identity layer; it is another surface product.
- NRW does not appear to publish a ready-to-use telecom clutter raster.

## NRW Dataset Assessment

| Dataset | What it tells us | What it does not tell us | Recommended role |
| --- | --- | --- | --- |
| `DGM1` | Bare-earth elevation | Any clutter identity | Ground baseline |
| `DOM1` | Top-of-surface elevation including buildings and vegetation | Whether the obstruction is a tree, building, mast, or other object | Profile obstruction surface |
| `nDOM50` | Relative object height above terrain | Object type | Secondary height check |
| `LoD1` | Simplified building geometry | Vegetation or non-building clutter type | Building fallback |
| `LoD2` | Building geometry and building identity | Vegetation or non-building clutter type | Primary building classifier |
| `Basis-DLM` | Broad topographic object classes such as forest, settlement, roads, and open land | Per-pixel RF clutter identity | Broad non-building clutter classifier |
| `bDOM50` | Image-based surface model from image correlation | Building identity or semantic clutter classes | Not recommended for classification |

## Practical Ellipse Strategy

Use this priority order:

1. `DGM1` for ground
2. `DOM1` for obstruction top
3. `LoD2` for building identity
4. `Basis-DLM` for broad non-building clutter identity
5. `nDOM50` for optional relative height validation

Recommended classification flow:

1. Sample the profile from `DGM1` and `DOM1`.
2. Mark profile segments as obstructed where `DOM1 > DGM1`.
3. Test the obstructed point or segment against `LoD2`.
4. If it intersects `LoD2`, classify it as `building`.
5. If it does not intersect `LoD2`, query `Basis-DLM`.
6. Map the `Basis-DLM` class into the nearest Ellipse clutter bucket.

## Suggested Ellipse Mapping

| Source rule | Ellipse clutter bucket | Confidence |
| --- | --- | --- |
| `LoD2` intersect | `Building` | High |
| `Basis-DLM` forest / woodland / woody vegetation class | `Trees / Forest` | Medium |
| `Basis-DLM` settlement / residential class | `Urban / Residential clutter` | Medium |
| `Basis-DLM` industrial / commercial class | `Industrial clutter` | Medium |
| `Basis-DLM` road / rail / transport class | `Transport corridor` | Medium |
| `Basis-DLM` arable / grassland / open land class | `Open / Low clutter` | Medium |
| No reliable semantic match | `Unknown clutter` | Low |

## Limits

- `DOM1` alone cannot reconcile clutter identity.
- `nDOM50` improves height understanding but not semantic classification.
- `Basis-DLM` is broad topographic classification, not a telecom clutter raster.
- The final Ellipse clutter mapping will still be a derived interpretation layer,
  not a native NRW RF product.

## MultiPlanner Implication

The current NRW provider adapter in this repository supports `dgm1`, `dom1`,
and `lod2`, but not `nDOM50` or `Basis-DLM`. That means current NRW backend
support is enough for ground, surface, and building identification, but not yet
enough for broader clutter classification.

Relevant code:

- `apps/api/src/multiplanner_api/providers.py`
- `apps/api/src/multiplanner_api/nrw.py`

## Source Links

- NRW height models:
  `https://www.bezreg-koeln.nrw.de/geobasis-nrw/produkte-und-dienste/hoehenmodelle`
- NRW 3D building models:
  `https://www.bezreg-koeln.nrw.de/geobasis-nrw/produkte-und-dienste/3d-gebaeudemodelle`
- NRW Basis-DLM:
  `https://www.bezreg-koeln.nrw.de/geobasis-nrw/produkte-und-dienste/landschaftsmodelle/aktuelle-landschaftsmodelle/digitales-basis`
- Live DOM1 catalog:
  `https://www.opengeodata.nrw.de/produkte/geobasis/hm/dom1_tiff/dom1_tiff/index.xml`
- Live LoD2 catalog:
  `https://www.opengeodata.nrw.de/produkte/geobasis/3dg/lod2_gml/lod2_gml/index.xml`
- Live nDOM50 catalog:
  `https://www.opengeodata.nrw.de/produkte/geobasis/hm/ndom50_tiff/ndom50_tiff/index.xml`
- Live Basis-DLM catalog:
  `https://www.opengeodata.nrw.de/produkte/geobasis/lm/akt/basis-dlm/index.xml`
- Live bDOM50 catalog:
  `https://www.opengeodata.nrw.de/produkte/geobasis/hm/bdom50_las/bdom50_las/index.xml`
