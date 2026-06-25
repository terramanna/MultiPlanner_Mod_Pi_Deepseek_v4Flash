import assert from "node:assert/strict";
import { requestLeafletSubset } from "../src/leaflet-subset-request.js";

function fakeDocument() {
  const tileList = { innerHTML: "", textContent: "" };
  return {
    getElementById: (id) => id === "tileList" ? tileList : null,
    querySelectorAll: () => [{ value: "dgm1" }],
    tileList,
  };
}

function baseContext(response) {
  const doc = fakeDocument();
  return {
    apiBaseUrl: "http://api.invalid",
    currentGeometry: () => ({ kind: "point", lon: 7.46, lat: 52.32 }),
    document: doc,
    downloadStatus: { textContent: "" },
    fetch: async () => response,
    state: { provider: "geobasis-nrw" },
  };
}

function previewPayload() {
  return {
    provider: "geobasis-nrw",
    results: [{ provider: "geobasis-nrw", dataset: "dgm1", match_count: 1, tiles: [{ provider: "geobasis-nrw", tile_id: "tile-a", primary_url: "https://example.invalid/tile.tif" }] }],
    total_estimated_source_bytes: 0,
    total_estimated_ellipse_bytes: 0,
  };
}

const okContext = baseContext({ ok: true, json: async () => previewPayload() });
await requestLeafletSubset(okContext, false);
assert.match(okContext.downloadStatus.textContent, /geobasis-nrw\/dgm1: 1 tiles/);
assert.match(okContext.document.tileList.innerHTML, /tile-a/);

const failContext = baseContext({ ok: false, json: async () => ({ detail: "Provider lookup failed for geobasis-nrw/dgm1: catalog unavailable" }) });
await requestLeafletSubset(failContext, false);
assert.equal(failContext.downloadStatus.textContent, "Subset lookup failed: Provider lookup failed for geobasis-nrw/dgm1: catalog unavailable");
