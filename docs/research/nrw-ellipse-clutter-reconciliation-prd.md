# NRW Ellipse Clutter Reconciliation PRD

This PRD turns the current conversation into an implementation-oriented document
for deriving usable clutter identity from NRW official datasets when an Ellipse
profile shows an obstruction.

Prepared from repository context and source review on 2026-06-28.

## Problem Statement

When a planner imports NRW terrain and surface data into Ellipse and generates a
path profile, clutter can appear in the profile without any reliable indication
of what that clutter actually is. The planner can see that an obstruction
exists, but cannot easily reconcile whether it is a building, vegetation, or a
broader land-cover condition.

This creates a planning gap:

- height data is available
- obstruction detection is available
- semantic clutter identity is missing

The user needs a documented strategy for combining NRW datasets into a derived
clutter identity workflow that is practical for Ellipse-oriented analysis.

## Solution

Use a layered NRW reconciliation approach instead of expecting a single clutter
dataset to solve the problem.

The solution combines:

- `DGM1` for ground elevation
- `DOM1` for top-of-surface elevation
- `LoD2` for building identity
- `Basis-DLM` for broad non-building clutter classes
- optional `nDOM50` for relative object height validation

This yields a derived classification workflow:

1. detect obstruction from `DOM1` relative to `DGM1`
2. classify as `building` if the obstruction intersects `LoD2`
3. otherwise infer a broad clutter class from `Basis-DLM`
4. use `nDOM50` only as a secondary confidence input for height, not identity

## User Stories

1. As a microwave planner, I want to know whether a profile obstruction is a building, so that I can judge whether the blockage is structurally stable and likely permanent.
2. As a microwave planner, I want to know whether a profile obstruction is vegetation, so that I can assess seasonal and growth-related risk.
3. As a microwave planner, I want a documented NRW-specific data strategy, so that I do not waste time testing unsuitable datasets.
4. As a planner using Ellipse, I want to distinguish height data from semantic clutter data, so that I do not assume `DOM1` encodes clutter type.
5. As a planner, I want to know whether NRW offers a ready-made clutter raster, so that I can decide whether derivation work is necessary.
6. As a planner, I want to treat buildings with higher confidence than other clutter types, so that permanent obstructions are identified correctly.
7. As a planner, I want broad non-building clutter categories when exact identity is unavailable, so that the profile is still interpretable.
8. As a product developer, I want a repeatable reconciliation order across NRW datasets, so that the workflow can later be automated.
9. As a backend developer, I want to know which NRW datasets are already supported in MultiPlanner, so that I can identify the current gap.
10. As a backend developer, I want to know which additional datasets would need adapters, so that future work can be scoped cleanly.
11. As a planning tool designer, I want a clear mapping from NRW classes to Ellipse clutter buckets, so that the resulting labels are usable in planner workflows.
12. As a planner, I want unknown or low-confidence clutter to remain explicitly unknown, so that the system does not overstate certainty.

## Implementation Decisions

- The workflow will treat `DGM1` and `DOM1` as elevation inputs only, not identity inputs.
- The workflow will treat `LoD2` as the authoritative NRW source for building identity.
- The workflow will treat `Basis-DLM` as a broad semantic layer for non-building clutter categories.
- The workflow will not treat `bDOM50` as a building dataset. It is a surface product and should not participate in semantic classification.
- The workflow will treat `nDOM50` as a relative-height support layer only.
- Derived clutter identity will be rule-based and priority-driven rather than pixel-native.
- Classification priority will be:
  1. `LoD2` building match
  2. `Basis-DLM` broad land-cover match
  3. unresolved fallback to `Unknown clutter`
- Suggested Ellipse clutter mapping will include:
  - `LoD2` intersect -> `Building`
  - `Basis-DLM` forest / woody vegetation -> `Trees / Forest`
  - `Basis-DLM` settlement -> `Urban / Residential clutter`
  - `Basis-DLM` industrial / commercial -> `Industrial clutter`
  - `Basis-DLM` transport -> `Transport corridor`
  - `Basis-DLM` open agricultural / grassland / open land -> `Open / Low clutter`
- The current repository support gap is explicit: the NRW adapter currently supports `dgm1`, `dom1`, and `lod2`, but not `Basis-DLM` or `nDOM50`.
- Any future automation should preserve confidence levels. `Building` can be treated as high confidence, while broad non-building clutter classes should remain medium confidence.

## Testing Decisions

- Good tests should validate external behavior and classification outcomes, not internal helper structure.
- Tests should prefer the highest seam possible:
  - classification input -> expected clutter bucket
  - obstruction context -> expected priority resolution
  - provider capability inventory -> expected dataset support
- Modules that would need testing in a future implementation:
  - NRW provider capability discovery
  - derived clutter classification rules
  - profile-to-identity reconciliation logic
  - confidence and fallback handling
- Tests should explicitly cover:
  - `LoD2` building hit overriding broader land-cover categories
  - non-building obstruction falling back to `Basis-DLM`
  - unresolved obstruction returning `Unknown clutter`
  - `DOM1` and `nDOM50` not being misused as semantic identity sources
- Prior art in this repository already exists for provider dataset inventory and provider-specific tile resolution, especially the NRW provider tests and the provider inventory tests.

## Out of Scope

- Creating a production-ready NRW clutter classifier in this turn
- Building new NRW adapters for `Basis-DLM` or `nDOM50`
- Publishing a new issue to the tracker
- Extending the Ellipse export pipeline
- Solving non-NRW clutter classification
- Claiming exact per-pixel vegetation species or object identity
- Treating NRW data as a native telecom clutter raster when it is only an input to one

## Further Notes

- The research note paired with this PRD is:
  `docs/research/nrw-ellipse-clutter-reconciliation.md`
- This PRD should be treated as a local planning artifact, not as evidence that
  implementation work has already been started.
- If this work moves from research to implementation, the next sensible step is
  to formalize a derived clutter schema with:
  - source dataset
  - source class or rule
  - Ellipse clutter bucket
  - priority
  - confidence
