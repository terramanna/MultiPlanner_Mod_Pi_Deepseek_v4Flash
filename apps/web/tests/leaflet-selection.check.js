import assert from "node:assert/strict";
import { clearLeafletSelection } from "../src/leaflet-selection.js";

const removed = [];
let redrawn = false;
let refreshed = false;
const state = {
  siteA: { lat: 1 },
  siteB: { lat: 2 },
  point: { lat: 3 },
  areaStart: { lat: 4 },
  rectangle: "rectangle-layer",
  manualLayer: "manual-layer",
  manualGeometry: { kind: "bbox" },
  activeSite: "A",
  searchSelectionActive: true,
};
const downloadStatus = { textContent: "" };
const tileList = { innerHTML: "tiles" };

clearLeafletSelection({
  state,
  map: { removeLayer: (layer) => removed.push(layer) },
  redrawGeometry: () => {
    redrawn = true;
  },
  refreshReadout: () => {
    refreshed = true;
  },
  downloadStatus,
  tileList,
  releaseProvider: () => {
    state.providerReleased = true;
  },
});

assert.deepEqual(removed, ["rectangle-layer", "manual-layer"]);
assert.equal(state.siteA, null);
assert.equal(state.siteB, null);
assert.equal(state.point, null);
assert.equal(state.areaStart, null);
assert.equal(state.rectangle, null);
assert.equal(state.manualLayer, null);
assert.equal(state.manualGeometry, null);
assert.equal(state.activeSite, null);
assert.equal(state.searchSelectionActive, false);
assert.equal(state.providerReleased, true);
assert.equal(redrawn, true);
assert.equal(refreshed, true);
assert.equal(downloadStatus.textContent, "Selection cleared.");
assert.equal(tileList.innerHTML, "");
