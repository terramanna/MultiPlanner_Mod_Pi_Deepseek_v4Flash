# Implementation TODO — MultiPlanner_Mod_Pi_Deepseek_v4Flash

Repo: `https://github.com/terramanna/MultiPlanner_Mod_Pi_Deepseek_v4Flash`
Upstream: `https://github.com/terramanna/MultiPlanner.git`
Branch: `main`

## Agent roles

| Agent | Role | Scope |
|-------|------|-------|
| **Agent 1 — Security** | Hardens network I/O, input validation, and file access. Works on `apps/api/src/multiplanner_api/` only. | SSRF, TLS, path traversal, model constraints |
| **Agent 2 — Standards & cleanup** | Kills dead code, consolidates duplicates, renames misnamed files. Works on both frontend and backend but isolated from security-sensitive code. | Provider geometry helpers, empty dirs, SSL fallback duplication, rename utils |
| **Agent 3 — Correctness & robustness** | Fixes cross-platform issues, test infrastructure, rate limiting. Works on `apps/api/src/multiplanner_api/main.py`, `models.py`, `tests/`. | `os.startfile`, `tkinter` test guard, rate limits, checksum verification |
| **Agent 4 — Renderer consolidation** | Works on `apps/web/src/` only. Chooses Cesium as default, archives MapLibre/Leaflet prototypes, replaces 23-chain test command. | Delete `maplibre-*`, `leaflet-nrw-probe.js`, simplify bootstrap, test runner script |

## Workflow

1. **Each agent works on a separate feature branch** from `main`:
   - `fix/security-ssrf-tls-validation`
   - `fix/standards-dead-code-duplication`
   - `fix/correctness-crossplatform-testing`
   - `fix/renderer-cesium-consolidation`
2. Agents run **independently** — no file conflicts between them.
3. After all agents finish, merge branches into `main` (or squash if small).
4. Run `npm test`, `pytest scripts/tests`, and `check_file_size_policy.py --all` before merging.

## Phase 1 — Security (~3h, parallelizable)

**Agent 1 only.**

- [x] Validate `primary_url` scheme/host before downloading
- [x] Remove universal TLS downgrade, use per-provider opt-in
- [x] Add symlink check in file/folder endpoints
- [x] Add finite/range constraints on all float input fields

## Phase 2 — Standards & maintainability (~6h, parallelizable)

**Agent 2 + Agent 4 can run in parallel here.**

- [x] Extract shared provider geometry helpers into one module (`request_geometry`, `_to_utm32/33`)
- [x] Delete empty `.gitkeep` scaffolding directories
- [x] Consolidate SSL fallback to `http_client.py` only
- [x] Rename `leaflet-prototype-utils.js` → `utils.js` and prune Leaflet-specific exports
- [x] Replace 23-chain test command with a small discover script
- [x] Choose renderer — default to Cesium; archive MapLibre/Leaflet prototypes

## Phase 3 — Correctness & robustness (~4h)

**Agent 3 only.**

- [x] Fix cross-platform `open-folder` — use `webbrowser.open` or `subprocess` for both OS
- [x] Fix `tkinter`-dependent tests or guard them with platform skip
- [x] Add rate limiting / concurrency cap to streaming endpoints
- [x] Add download checksum verification (SHA256 of downloaded tile)
- [x] Set up `src/` shared module properly (move reusable logic out of `apps/api`)

## Phase 4 — Future value (nice to have)

Not scheduled. Do when needed.

- [ ] Local project persistence (Phase 2 of roadmap)
- [ ] Authentication for hosted deployment
- [ ] Provider covered gap: NI adapter module, SL DOM1, etc.

## Status legend

- `[ ]` — not started
- `[x]` — done

## Notes

- After each phase, push to `origin` and verify CI passes.
- If a change contradicts an existing ADR, raise it — do not silently override.
- Use `.agents/pitfalls.md` — append entries if a skill causes a regression.