# Pitfalls

Append-only log of skill-specific regressions and anti-patterns.

Purpose:
- record what went wrong after using a skill
- capture the exact regression or cross-contamination that had to be undone
- prevent repeating the same failure in later runs

Rules:
- do not delete past entries
- do not rewrite history to make entries look cleaner
- append a new entry when a skill causes a regression, forces a redo, or contaminates another workflow
- prefer concrete "do not" statements tied to one skill and one observed failure

Entry shape:

```markdown
## 2026-06-25 - <skill-name>

- Do not <action> because it regressed <symptom>.
- Do not <action> because it forced a redo of <work>.
- Cross-contamination note: <what leaked into where>.
- Recovery: <what had to be redone>.
```

Current entries:

## 2026-06-25 - bootstrap / launcher scripts

- Do not rename documented Windows launcher filenames to space-separated variants if the real files still use underscores.
- Do not assume the README is stale without checking the actual batch files first.
- Cross-contamination note: the README briefly advertised `Start MultiPlanner.bat`, `Stop MultiPlanner.bat`, and `Restart MultiPlanner.bat`, which did not match the real launcher names.
- Recovery: the README launcher commands were rewritten to `Start_MultiPlanner.bat`, `Stop_MultiPlanner.bat`, and `Restart_MultiPlanner.bat`.

## 2026-06-25 - subset download / NRW TIFF fetch

- Do not assume `requests` will trust the NRW geodata TLS chain on this Windows setup.
- Do not treat a reachable URL as a successful backend download when certificate verification still fails in the Python client.
- Cross-contamination note: the backend returned 500 for DGM1 and DOM1 even though the same URLs answered 200 to `Invoke-WebRequest`.
- Recovery: `_download_file` now retries the TIFF fetch without certificate verification when the first request fails with `SSLError`.

## 2026-06-25 - browser save flow

- Do not rely on a typed path prompt in a browser app when the user needs a save location.
- Do not try to make the backend write directly to an arbitrary client path that the browser cannot reveal.
- Cross-contamination note: the first save-location attempt pushed an `output_dir` string through the backend, which did not satisfy the folder-picker requirement.
- Recovery: the UI now uses a directory picker and copies the backend-generated cached files into the selected folder.

## 2026-06-25 - Ellipse export projection

- Do not make the Ellipse export dynamically choose UTM zones by location.
- Do not "fix" NRW or eastern Germany exports to UTM 33N for GIS correctness when the target import is Ellipse.
- Cross-contamination note: Ellipse appears to support one active project projection at a time; this workflow expects WGS 84 / UTM zone 32N even when source data could reasonably map to another zone.
- Recovery: keep `ellipse_mapinfo_tab` exports warped to `EPSG:32632` and keep the MapInfo `.TAB` CoordSys aligned with UTM 32N unless a separate, explicitly named non-Ellipse export profile is added.

## 2026-06-25 - browser save flow

- Do not copy all selected DGM1/DOM1 source tiles and Ellipse exports in one unbounded browser `Promise.all`.
- Do not name combined Ellipse exports only `dom1.tif` or `dgm1.tif`.
- Cross-contamination note: parallel browser copies can partially complete and make it look like one selected dataset vanished from the user-selected folder. Ambiguous export names also hide that `utm32/dom1.tif` is the merged Ellipse output.
- Recovery: copy browser-saved files deterministically and name Ellipse exports with selection, dataset, tile count, and projection profile.

## 2026-06-25 - cross-border provider downloads

- Do not force a corridor to use one selected provider when the link can cross a state/provider boundary.
- Do not send long ArcGIS corridor polygons as GET query strings; LGLN can return 404 for long URLs even when the FeatureServer is valid.
- Do not let one provider failure abort an automatic multi-provider lookup or download when another provider can still return useful tiles.
- Cross-contamination note: the Lower Saxony/NRW test link needs LGLN and NRW queried independently, with unsupported datasets skipped and provider failures reported as warnings.
- Recovery: use `provider: "auto"` for cross-border links, POST ArcGIS queries, normalize provider-returned values to strings, and keep source tile folders grouped by provider.

## 2026-06-25 - subset naming and size warnings

- Do not rely only on generated geometry names like `leaflet_corridor` for saved files.
- Do not leave a blank job/file name to fall back to an opaque technical name.
- Do not start large downloads or Ellipse merges without showing an estimated source size and merged-export size first.
- Cross-contamination note: ambiguous filenames make it hard to identify which customer/site/link a saved terrain bundle belongs to later. Missing size warnings also make whole-region merges look safe when they can be tens or hundreds of GB.
- Recovery: expose a user-entered job/file name, default blank names by geometry (`siteA_siteB_link_Xkm_150m_corridor_1m_merge`, `circle_Xkm_diameter_1m_merge`, `rectangle_Xkm_Ykm_1m_merge`), return estimate fields from preview/download APIs, and require confirmation for large estimated downloads/exports.
