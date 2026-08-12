# Main Integration TODO

Goal: make `origin/main` the lead tree containing all retained, working changes,
without losing work currently held only in dirty checkouts or stale branches.

Follow `docs/agents/git-workflow.md` throughout. Use focused branches, explicit
staging, attributable commits, normal merges, and no squash merges.

## 1. Secure the current work

- [ ] Record the current branch, status, worktrees, and commit IDs.
- [ ] Export the tracked dirty diff as a binary patch outside the repository.
- [ ] Back up the untracked browser launcher and PySide6 prototype source files.
- [ ] Exclude `.tools/`, generated rasters, caches, and the webinar from source backups.
- [ ] Verify the backup before switching branches or removing worktrees.
- [ ] Confirm the Git identity matches an actor in `config/commit-actors.json`.

## 2. Establish the lead main worktree

- [ ] Create a clean worktree dedicated to `main`.
- [ ] Fetch and fast-forward `main` to `origin/main`.
- [ ] Confirm local `main` and `origin/main` point to the same commit.
- [ ] Run baseline Python tests, web tests, Ruff, ESLint, build, and size policy.
- [ ] Fix the Windows-invalid cache-eviction test timestamps on a test-only branch.
- [ ] Merge the test fix normally and push `main`.

## 3. Integrate current WIP in focused branches

Every branch below must start from the latest `main`. Run focused checks, stage
only related paths, push the branch, merge without squashing, and push `main`
before beginning the next branch.

### 3.1 Launcher runtime reliability

Branch: `fix/launcher-runtime-reliability`

- [ ] Port the service lifecycle and thread-safety changes.
- [ ] Port project-local Node and Vite execution changes.
- [ ] Make `bootstrap_local.ps1` provision the runtime required by the launchers,
      or revise the launchers to use the runtime that bootstrap already supports.
- [ ] Preserve the underscore-based launcher filenames.
- [ ] Verify start, stop, restart, duplicate-widget handling, and setup diagnostics.
- [ ] Verify launcher behavior from a fresh bootstrap.
- [ ] Commit, push, merge, and push `main`.

### 3.2 Isolated Edge browser

Branch: `fix/isolated-edge-browser`

- [ ] Port `scripts/browser_launcher.py` and its regression tests.
- [ ] Route automatic opening and the Tk widget Open button through it.
- [ ] Retain `--user-data-dir`, `--no-first-run`, and
      `--no-default-browser-check`.
- [ ] Verify the browser opens once after both services become healthy.
- [ ] Verify ordinary signed-in Edge profiles remain untouched.
- [ ] Commit, push, merge, and push `main`.

### 3.3 Network-search fallback

Branch: `fix/network-search-empty-db-fallback`

- [ ] Port fallback from an empty configured database to static GeoJSON.
- [ ] Port its focused regression test.
- [ ] Commit, push, merge, and push `main`.

### 3.4 Link-profile improvements

Branch: `feat/link-profile-followups`

- [ ] Port independent antenna heights for sites A and B.
- [ ] Port GHz-to-MHz UI conversion.
- [ ] Port background profile preloading and stale-request protection.
- [ ] Port bounded parallel terrain probes.
- [ ] Port probe caching and per-source download locking.
- [ ] Verify provider-selection behavior remains unchanged.
- [ ] Run the API profile tests and both link-profile web checks.
- [ ] Use no more than three cohesive commits.
- [ ] Push, merge without squashing, and push `main`.

### 3.5 Resumable downloads and progress

Branch: `feat/resumable-subset-downloads`

- [ ] Port HTTP Range-based `.part` download resumption.
- [ ] Port per-tile progress metadata and browser progress display.
- [ ] Fix accounting so failed or missing-URL tiles reach a terminal progress state.
- [ ] Port directory and job naming behavior.
- [ ] Preserve deterministic copying and provider-grouped output.
- [ ] Test resumed, restarted, failed, partial, and successful downloads.
- [ ] Commit, push, merge, and push `main`.

### 3.6 Categorical and clutter export

Branch: `feat/categorical-raster-export`

- [ ] Identify the real provider and dataset route supplying categorical rasters.
- [ ] If no route is planned, preserve the patch externally and defer the branch.
- [ ] If proceeding, port nearest-neighbour warping, fixed grid resolution,
      palette validation, and nearest-neighbour pyramids.
- [ ] Add an end-to-end `_export_ellipse_dataset` test.
- [ ] Preserve the Ellipse WGS 84 / UTM zone 32N invariant.
- [ ] Commit, push, merge, and push `main`.

## 4. Resolve prototypes and local artifacts

### PySide6 widget

- [ ] Decide whether to discard it, archive it externally, or productize it.
- [ ] If productized, declare PySide6 as a dependency.
- [ ] Route its Open button through the isolated Edge launcher.
- [ ] Add lifecycle tests equivalent to the supported Tk widget.
- [ ] Keep this work separate from the supported launcher branches.

### Local artifacts

- [ ] Add suitable ignore rules for `.tools/` and `.tmp_semantic_test/`.
- [ ] Move `archive/video/webinar.mp4` outside the repository or explicitly adopt
      Git LFS; do not commit the large file to ordinary Git history.
- [ ] Confirm no generated TIFF, cache, runtime, database, or video is staged.

## 5. Reconcile old worktrees

- [ ] Compare `MultiPlanner-cesium-worktree` WIP with current `main`.
- [ ] Port only still-relevant Cesium behavior onto a fresh branch from `main`.
- [ ] Compare `MultiPlanner-maplibre-worktree` WIP with current MapLibre code.
- [ ] Port only still-relevant MapLibre work onto a fresh branch from `main`.
- [ ] Confirm the old Bavaria provider branch is superseded by current code.
- [ ] Compare the two unique `test/maplibre-prototype` commits before retirement.
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
