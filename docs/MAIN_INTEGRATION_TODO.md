# Main Integration TODO

Goal: make `origin/main` the lead tree containing all retained, working changes,
without losing work currently held only in dirty checkouts or stale branches.

Follow `docs/agents/git-workflow.md` throughout. Use focused branches, explicit
staging, attributable commits, normal merges, and no squash merges.

## Current status and safety notes

`origin/main` is the lead tree. Integrated work includes the launcher,
isolated-browser, network-search, link-profile, resumable-download, semantic
clutter, separate building/tree GRC, MapLibre DOM hillshade, and generalized
Cesium geometry work. The completed `fix/leaflet-planner-controls` branch adds
the retained Leaflet planning-control, search, and provider-selection updates.

- Do not clean the primary dirty worktree before resolving section 3.6. Its
  categorical export implementation exists only in that dirty diff and in the
  verified external recovery backup. The helper-level nearest-neighbour test
  exists, but the real provider/dataset route and an end-to-end export test do
  not.
- Do not trust imports from the shared root `.venv` when testing another
  worktree. Its editable install points at the primary checkout and can produce
  false `ModuleNotFoundError` failures. Set `PYTHONPATH` to the worktree's
  `apps/api/src`, or create a worktree-local environment.
- The primary checkout still contains ignored `archive/video/webinar.mp4`
  (about 407 MiB) and `.tools/node` (about 143 MiB). External archival of the
  webinar remains pending; continue to stage explicit paths only.
- The untracked PySide6 status-widget prototype and launcher are preserved in
  the recovery backup, but the productize/archive decision remains open.
- Fresh-worktree bootstrap uses pip's system trust store and stops on native
  command failure. It completed successfully in a disposable worktree after the
  external proxy was disabled on 2026-08-13.

## 1. Secure the current work

- [x] Record the current branch, status, worktrees, and commit IDs.
- [x] Export the tracked dirty diff as a binary patch outside the repository.
- [x] Back up the untracked browser launcher and PySide6 prototype source files.
- [x] Exclude `.tools/`, generated rasters, caches, and the webinar from source backups.
- [x] Verify the backup before switching branches or removing worktrees.
- [x] Confirm the Git identity matches an actor in `config/commit-actors.json`.

## 2. Establish the lead main worktree

- [x] Create a clean worktree dedicated to `main`.
- [x] Fetch and fast-forward `main` to `origin/main`.
- [x] Confirm local `main` and `origin/main` point to the same commit.
- [x] Run baseline Python tests, web tests, Ruff, ESLint, build, and size policy.
- [x] Fix the Windows-invalid cache-eviction test timestamps on a test-only branch.
- [x] Merge the test fix normally and push `main` (`1b02f7b`).

## 3. Integrate current WIP in focused branches

Every branch below must start from the latest `main`. Run focused checks, stage
only related paths, push the branch, merge without squashing, and push `main`
before beginning the next branch.

### 3.1 Launcher runtime reliability

Branch: `fix/launcher-runtime-reliability`

- [x] Port the service lifecycle and thread-safety changes.
- [x] Port project-local Node and Vite execution changes.
- [x] Make `bootstrap_local.ps1` provision the runtime required by the launchers,
      or revise the launchers to use the runtime that bootstrap already supports.
- [x] Preserve the underscore-based launcher filenames.
- [x] Verify start, stop, restart, duplicate-widget handling, and setup diagnostics.
- [x] Verify launcher behavior from a fresh bootstrap: API and web reached HTTP
      200, duplicate start retained one widget instance and one service pair,
      Edge used the isolated profile flags, stop cleared both listeners and the
      PID registry, and restart returned both services to HTTP 200.
- [x] Commit, push, merge, and push `main` (`bf9e576`).

### 3.2 Isolated Edge browser

Branch: `fix/isolated-edge-browser`

- [x] Port `scripts/browser_launcher.py` and its regression tests.
- [x] Route automatic opening and the Tk widget Open button through it.
- [x] Retain `--user-data-dir`, `--no-first-run`, and
      `--no-default-browser-check`.
- [x] Verify the browser opens once after both services become healthy.
- [x] Verify ordinary signed-in Edge profiles remain untouched.
- [x] Commit, push, merge, and push `main` (`e237153`).

### 3.3 Network-search fallback

Branch: `fix/network-search-empty-db-fallback`

- [x] Port fallback from an empty configured database to static GeoJSON.
- [x] Port its focused regression test.
- [x] Commit, push, merge, and push `main` (`abd84b7`).

### 3.4 Link-profile improvements

Branch: `feat/link-profile-followups`

- [x] Port independent antenna heights for sites A and B.
- [x] Port GHz-to-MHz UI conversion.
- [x] Port background profile preloading and stale-request protection.
- [x] Port bounded parallel terrain probes.
- [x] Port probe caching and per-source download locking.
- [x] Verify provider-selection behavior remains unchanged.
- [x] Run the API profile tests and both link-profile web checks.
- [x] Use no more than three cohesive commits.
- [x] Push, merge without squashing, and push `main` (`ea022b5`).

### 3.5 Resumable downloads and progress

Branch: `feat/resumable-subset-downloads`

- [x] Port HTTP Range-based `.part` download resumption.
- [x] Port per-tile progress metadata and browser progress display.
- [x] Fix accounting so failed or missing-URL tiles reach a terminal progress state.
- [x] Port directory and job naming behavior.
- [x] Preserve deterministic copying and provider-grouped output.
- [x] Test resumed, restarted, failed, partial, and successful downloads.
- [x] Commit, push, merge, and push `main` (`f726e01`).

### 3.6 Categorical and clutter export

Branch: `feat/categorical-raster-export`

- [ ] Identify the real provider and dataset route supplying categorical rasters.
- [x] Preserve the stranded dirty patch in the verified external backup.
- [x] Defer the token-based categorical export patch until a real provider and
      dataset route exists; the separate MapInfo GRC workflow covers the current
      Ellipse building/tree requirement without speculative dataset detection.
- [ ] If proceeding, port nearest-neighbour warping, fixed grid resolution,
      palette validation, and nearest-neighbour pyramids.
- [ ] Add an end-to-end `_export_ellipse_dataset` test.
- [ ] Preserve the Ellipse WGS 84 / UTM zone 32N invariant.
- [ ] Commit, push, merge, and push `main`.

### 3.7 Separate Ellipse GRC layers

Branch: `feat/separate-ellipse-grc`

- [x] Convert the shared semantic mask through the installed MapInfo Raster API.
- [x] Export LoD2 buildings as a building-only classified GRC.
- [x] Export forest and woodland as a separate tree-only classified GRC.
- [x] Make unrelated cells No Data in each output.
- [x] Verify class labels, palettes, and cell values with a live MapInfo/GDAL smoke test.
- [x] Add orchestration tests and update the Ellipse workflow documentation.
- [x] Commit, push, merge, and push `main` (`e5586d8`).

### 3.8 Leaflet planning controls and universal search

Branch: `fix/leaflet-planner-controls`

- [x] Move the planning-mode selector into the left panel and remove the
      experimental Cesium comparison link from the normal planner controls.
- [x] Restrict Geoman drawing controls and measurement guidance to area mode.
- [x] Restore a compact top-centre universal search with All, Sites, Links, and
      Places filters.
- [x] Balance All network results as up to five sites followed by five links;
      return up to ten results for a focused Sites or Links search.
- [x] Preserve city, town, address, postcode, and coordinate lookup through the
      Places filter and place geographic results before network matches in All.
- [x] Route browser search through the same-origin Vite `/api` proxy.
- [x] Update results after two typed characters with a 250 ms debounce and
      cancel stale requests.
- [x] Detect the provider from the current point, corridor, rectangle, circle,
      or polygon while preserving explicit manual provider selection.
- [x] Release search-derived sites or links on an empty-map click and reset the
      provider to automatic detection; do not release when clicking the selected
      marker or link itself.
- [x] Verify focused API search tests, web tests, ESLint, production build,
      diff checks, and repository size policy.

## 4. Resolve prototypes and local artifacts

### PySide6 widget

- [x] Archive it externally in the verified integration backup. The supported
      Tk widget is current; do not add a second GUI runtime without a product
      decision and dependency plan.
- [ ] If productized, declare PySide6 as a dependency.
- [ ] Route its Open button through the isolated Edge launcher.
- [ ] Add lifecycle tests equivalent to the supported Tk widget.
- [ ] Keep this work separate from the supported launcher branches.

### Local artifacts

- [x] Add suitable ignore rules for `.tools/`, `.tmp_semantic_test/`, and local
      webinar MP4 files.
- [x] Move `archive/video/webinar.mp4` outside the repository or explicitly adopt
      Git LFS; do not commit the large file to ordinary Git history.
- [ ] Confirm no generated TIFF, cache, runtime, database, or video is staged.

## 5. Reconcile old worktrees

- [x] Compare `MultiPlanner-cesium-worktree` WIP with current `main`.
- [x] Port only still-relevant Cesium behavior onto fresh branches from `main`:
      generalized geometry/provider controls were retained without replacing
      the newer link-profile and resumable-download implementations.
- [x] Compare `MultiPlanner-maplibre-worktree` WIP with current MapLibre code.
- [x] Port only still-relevant MapLibre work onto a fresh branch from `main`:
      the missing `dom1hs` backend route was retained; unwired Geoman/preview
      experiments remain preserved in the backup rather than entering main.
- [x] Confirm the old Bavaria provider branch is superseded by current code.
- [x] Compare the two unique `test/maplibre-prototype` commits before retirement;
      their older NRW subset prototype is superseded by the current terrain
      prototype and the supported Leaflet subset workflow.
- [ ] Prune missing worktree metadata only after confirming its commits are safe.

## 6. Clean merged branches and worktrees

Do this only after all desired work is reachable from `origin/main`.

- [ ] Remove the redundant semantic-clutter worktree.
- [ ] Remove fully merged local branches:
  - `feat/multiplanner-link-profile-window`
  - `feat/bayern-semantic-clutter`
  - `feat/leaflet-nrw-probe`
  - `fix/prototype-provider-retry`
  - `FEAT_WMS_NRW`
  - `feat/cesium-planning-shell`
- [ ] Remove corresponding merged remote branches where appropriate.
- [ ] Remove obsolete unmerged branches only after explicit comparison.
- [ ] Run `git worktree prune` after valuable worktrees are reconciled.

## Definition of done

- [ ] The primary checkout is clean and on `main`.
- [ ] Local `main` exactly matches `origin/main`.
- [ ] All retained functionality is reachable from `origin/main`.
- [ ] No valuable work exists only in a dirty worktree, stash, patch, or untracked file.
- [ ] Python tests, web tests, Ruff, ESLint, build, and size checks pass.
- [ ] Fresh-clone bootstrap and Windows launcher smoke tests pass.
- [ ] No stale worktrees, redundant branches, generated artifacts, or oversized
      media remain inside the repository.
