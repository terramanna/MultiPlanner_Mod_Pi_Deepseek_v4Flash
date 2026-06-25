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
    confirm: () => true,
    currentGeometry: () => ({ kind: "point", lon: 7.46, lat: 52.32 }),
    document: doc,
    downloadStatus: { textContent: "" },
    fetch: async () => response,
    jobNameInput: { value: "" },
    map: {},
    openDownloadFolderButton: { hidden: true },
    openFolderAfterDownload: { checked: false },
    providerCoverage: {},
    selectedExportProfile: () => "ellipse_grd",
    state: { provider: "geobasis-nrw", coverageFeatures: {}, lastDownloadedOutputDir: null },
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

const boundContext = baseContext({ ok: true, json: async () => previewPayload() });
boundContext.fetch = async function () {
  assert.equal(this, globalThis);
  return { ok: true, json: async () => previewPayload() };
};
await requestLeafletSubset(boundContext, false);
assert.match(boundContext.downloadStatus.textContent, /geobasis-nrw\/dgm1: 1 tiles/);

function recordingDownloadContext(responses) {
  const context = baseContext(null);
  const statusMessages = [];
  context.fetch = async () => responses.shift();
  Object.defineProperty(context.downloadStatus, "textContent", {
    get: () => statusMessages.at(-1) || "",
    set: (value) => statusMessages.push(value),
  });
  return { context, statusMessages };
}

function downloadPayload() {
  return {
    provider: "geobasis-nrw",
    selection_name: "point_n52_3200_e7_4600_1m_merge",
    output_dir: "cache/saved_subsets/point_n52_3200_e7_4600_1m_merge",
    files: [],
    exports: [],
    warnings: [],
  };
}

function fakeDirectoryHandle(name = "downloads") {
  return {
    name,
    getDirectoryHandle: async (childName) => fakeDirectoryHandle(childName),
  };
}

const originalWindow = globalThis.window;
globalThis.window = {
  showDirectoryPicker: async () => fakeDirectoryHandle(),
};
const { context: downloadContext, statusMessages } = recordingDownloadContext([
  { ok: true, json: async () => previewPayload() },
  { ok: true, json: async () => downloadPayload() },
]);
await requestLeafletSubset(downloadContext, true);
assert.deepEqual(statusMessages, [
  "Checking selected 1 m tiles...",
  "Choose an output folder to start the download/export.",
  "Downloading source tiles and building export...",
  "Saving downloaded files to the selected folder...",
  "Saved 0 source files and 0 GRD exports to downloads\\point_n52_3200_e7_4600_1m_merge.",
]);
globalThis.window = originalWindow;
