import assert from "node:assert/strict";
import { applyProviderSelection, coverageShouldShow, providerDatasets } from "../src/provider-selection.js";

const providers = [
  { name: "auto", datasets: ["dgm1", "dom1", "dop20"] },
  { name: "lgln-ni", datasets: ["dgm1", "dom1", "dop20"] },
  { name: "geobasis-nrw", datasets: ["dgm1", "dom1"] },
];

assert.equal(coverageShouldShow("auto", "lgln-ni", true), true);
assert.equal(coverageShouldShow("geobasis-nrw", "lgln-ni", true), false);
assert.equal(coverageShouldShow("geobasis-nrw", "geobasis-nrw", true), true);
assert.equal(coverageShouldShow("geobasis-nrw", "geobasis-nrw", false), false);
assert.deepEqual(providerDatasets(providers, "geobasis-nrw"), ["dgm1", "dom1"]);

const state = { provider: "auto" };
const providerSelect = { value: "geobasis-nrw" };
let renderedDatasets = [];
let overlayUpdates = 0;
let cleared = false;

const selected = applyProviderSelection({
  state,
  providerSelect,
  providers,
  renderDatasetChoices: (datasets) => {
    renderedDatasets = datasets;
  },
  updateCoverageOverlay: () => {
    overlayUpdates += 1;
  },
  clearTiles: () => {
    cleared = true;
  },
});

assert.equal(selected, "geobasis-nrw");
assert.equal(state.provider, "geobasis-nrw");
assert.equal(providerSelect.value, "geobasis-nrw");
assert.deepEqual(renderedDatasets, ["dgm1", "dom1"]);
assert.equal(overlayUpdates, 1);
assert.equal(cleared, true);
