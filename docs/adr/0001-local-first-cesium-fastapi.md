# ADR 0001: Local-First Cesium + FastAPI Architecture

## Status

Accepted

## Context

MultiPlanner targets terrain-aware telecom planning with DTM/DOM subset fetch
and LOS analysis as the first product value. The product must serve both:

- an individual planner running locally
- a future hosted multi-planner deployment

The frontend direction is Cesium because the long-term product value is terrain-
aware and 3D-centric, especially for wireless and cellular planning.

## Decision

Use:

- Cesium for the web frontend
- FastAPI for the backend
- a local-first deployment model where both run on localhost in v1
- a provider adapter layer for state-specific geodata access

## Consequences

Positive:

- v1 and hosted editions can share contracts
- Cesium aligns with the long-term wireless/cellular planning direction
- heavy geodata and LOS logic stays out of the frontend
- provider-specific complexity remains isolated

Negative:

- frontend setup is more complex than a simple 2D web map
- a local web-serving workflow is required even for single-user mode
- provider integration work must be disciplined to avoid coupling
