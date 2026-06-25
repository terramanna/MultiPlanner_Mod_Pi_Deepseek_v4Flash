import assert from "node:assert/strict";
import { loadProviderCoverageCache, saveProviderCoverageCache } from "../src/provider-coverage-cache.js";

function createStorage() {
  const entries = new Map();
  return {
    getItem(key) {
      return entries.has(key) ? entries.get(key) : null;
    },
    setItem(key, value) {
      entries.set(key, String(value));
    },
  };
}

const storage = createStorage();
const featuresByProvider = {
  "lgln-ni": { type: "Feature", properties: { lkz: "NI" }, geometry: null },
  "geobasis-nrw": { type: "Feature", properties: { lkz: "NW" }, geometry: null },
};

saveProviderCoverageCache(featuresByProvider, storage);
assert.deepEqual(loadProviderCoverageCache(storage), featuresByProvider);
assert.equal(loadProviderCoverageCache({ getItem: () => "{bad json" }), null);
assert.equal(loadProviderCoverageCache({ getItem: () => JSON.stringify({ version: 2, featuresByProvider }) }), null);
