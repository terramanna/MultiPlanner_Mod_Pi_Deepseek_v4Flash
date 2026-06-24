# Legacy Source Map

This repository was started fresh from `Project_Foundation_Template`, but the
older `multi_planner` repository contains useful research and planning work that
should inform the new build without being copied wholesale.

Local reference clone:

- `H:\VSC_Projects\Coding_Projects\multi_planner_legacy`

## High-value legacy documents

- `Orchestration/01_PRD.md`
  Broad product requirements and telecom workflow ambition.
- `Orchestration/02_TECHNICAL_ARCHITECTURE.md`
  Earlier Cesium + Python architecture direction.
- `docs/12_los_visibility_analysis.md`
  Deep LOS/viewshed problem framing and feature inventory.
- `docs/23_ui_concept_pack_beta.md`
  UI direction exploration that may influence the Cesium planner shell.
- `docs/24_mapping_choice_config.md`
  Notes relevant to frontend mapping choices.
- `docs/26_step1_site_ingestion_los_ux_data.md`
  Likely relevant for the first-value-loop around site ingestion and LOS UX.

## What to reuse

- terminology and problem framing
- product sequencing ideas
- LOS and viewshed analysis requirements
- useful UI research

## What not to reuse blindly

- broad multi-domain scope that dilutes the first release
- old file layout and naming without checking whether it still serves the narrowed goal
- assumptions that ignore streamed/subset 1 m terrain access

## Current interpretation

The new repo narrows the first build target to:

1. subset fetch of 1 m DTM/DOM/imagery
2. LOS and path-profile analysis
3. Cesium local planner workflow

Legacy documents remain a source of ideas, not source of truth.
