import assert from "node:assert/strict";
import { applyProviderSelection, coverageShouldShow, providerDatasets, sortProviders } from "../src/provider-selection.js";

const providers = [
  { name: "auto", label: "Auto (split by provider)", datasets: ["dgm", "dgm1", "dom", "dom1", "dop20"] },
  { name: "lgln-ni", label: "LGLN Lower Saxony", datasets: ["dgm1", "dom1", "dop20"] },
  { name: "geobasis-nrw", label: "Geobasis NRW", datasets: ["dgm1", "dom1"] },
];

assert.equal(coverageShouldShow("auto", "lgln-ni", true), true);
assert.equal(coverageShouldShow("geobasis-nrw", "lgln-ni", true), false);
assert.equal(coverageShouldShow("geobasis-nrw", "geobasis-nrw", true), true);
assert.equal(coverageShouldShow("geobasis-nrw", "geobasis-nrw", false), false);
assert.deepEqual(providerDatasets(providers, "auto"), ["dgm1", "dom1", "dop20"]);
assert.deepEqual(providerDatasets(providers, "geobasis-nrw"), ["dgm1", "dom1"]);
assert.deepEqual(
  sortProviders([
    providers[0],
    { name: "z-last", label: "Zulu Provider", datasets: [] },
    { name: "a-first", label: "Alpha Provider", datasets: [] },
  ], "asc").map((provider) => provider.name),
  ["auto", "a-first", "z-last"],
);
assert.deepEqual(
  sortProviders([
    providers[0],
    { name: "z-last", label: "Zulu Provider", datasets: [] },
    { name: "a-first", label: "Alpha Provider", datasets: [] },
  ], "desc").map((provider) => provider.name),
  ["auto", "z-last", "a-first"],
);

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
