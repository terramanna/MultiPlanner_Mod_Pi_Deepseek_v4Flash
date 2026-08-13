import assert from "node:assert/strict";
import { applySearchCandidateToState, searchPlacementTarget } from "../src/leaflet-search-results.js";

const emptyState = { activeSite: null, siteA: null, siteB: null };
assert.equal(searchPlacementTarget(emptyState), "A");
assert.equal(searchPlacementTarget({ ...emptyState, siteA: { lat: 1, lon: 2 } }), "B");
assert.equal(searchPlacementTarget({ ...emptyState, activeSite: "B" }), "B");

const state = { activeSite: null, siteA: null, siteB: null };
const redraws = [];
const refreshes = [];
applySearchCandidateToState({
  candidate: { source: "nominatim", lat: 52.0, lon: 7.0 },
  state,
  variant: "corridor",
  redrawGeometry: () => redraws.push(true),
  refreshReadout: () => refreshes.push(true),
});

assert.deepEqual(state.siteA, { lat: 52.0, lon: 7.0 });
assert.equal(state.activeSite, null);
assert.equal(state.searchSelectionActive, true);
assert.equal(redraws.length, 1);
assert.equal(refreshes.length, 1);

applySearchCandidateToState({
  candidate: {
    source: "network-link",
    link_name: "HND_A_B",
    site_a_lat: 51.0,
    site_a_lon: 7.1,
    site_a_name: "SITE_A",
    site_a_id: "S1",
    site_a_structure: "Mast",
    site_b_lat: 51.5,
    site_b_lon: 7.6,
    site_b_name: "SITE_B",
    site_b_id: "S2",
    site_b_structure: "Dach",
  },
  state,
  variant: "corridor",
  redrawGeometry: () => redraws.push(true),
  refreshReadout: () => refreshes.push(true),
});

assert.deepEqual(state.siteA, { lat: 51.0, lon: 7.1, name: "SITE_A", label: "", id: "S1", type: "", structure: "Mast" });
assert.deepEqual(state.siteB, { lat: 51.5, lon: 7.6, name: "SITE_B", label: "", id: "S2", type: "", structure: "Dach" });
assert.equal(state.selectedNetworkLink.link_name, "HND_A_B");
assert.equal(state.searchSelectionActive, true);
