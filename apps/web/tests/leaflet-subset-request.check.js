import assert from "node:assert/strict";
import { datasetsForExport, missingDownloadPrompt, requestLeafletSubset } from "../src/leaflet-subset-request.js";

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
    downloadProgress: { hidden: true, max: 1, value: 0 },
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
  const requests = [];
  context.fetch = async (url, options) => {
    requests.push({ url, options });
    return responses.shift();
  };
  Object.defineProperty(context.downloadStatus, "textContent", {
    get: () => statusMessages.at(-1) || "",
    set: (value) => statusMessages.push(value),
  });
  return { context, requests, statusMessages };
}

function downloadPayload() {
  return {
    provider: "geobasis-nrw",
    selection_name: "point_n52_3200_e7_4600_1m_merge",
    output_dir: "cache/saved_subsets/point_n52_3200_e7_4600_1m_merge",
    files: [],
    failed_downloads: [],
    exports: [],
    warnings: [],
  };
}

function failedDownloadPayload() {
  return {
    ...downloadPayload(),
    failed_downloads: [
      { provider: "geobasis-nrw", dataset: "dgm1", tile_id: "tile-b", reason: "network timeout" },
    ],
  };
}

function fakeStreamResponse(result) {
  const sse = `data: ${JSON.stringify({ type: "done", result })}\n\n`;
  const bytes = new TextEncoder().encode(sse);
  let consumed = false;
  return {
    ok: true,
    body: {
      getReader() {
        return {
          async read() {
            if (consumed) return { done: true, value: undefined };
            consumed = true;
            return { done: false, value: bytes };
          },
        };
      },
    },
  };
}

function fakeProgressStreamResponse(result) {
  const events = [
    { type: "progress", provider: "geobasis-nrw", dataset: "dgm1", tile_id: "tile-a", current: 1, total: 1, success: true },
    { type: "done", result },
  ];
  const bytes = new TextEncoder().encode(events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(""));
  let consumed = false;
  return {
    ok: true,
    body: {
      getReader() {
        return {
          async read() {
            if (consumed) return { done: true, value: undefined };
            consumed = true;
            return { done: false, value: bytes };
          },
        };
      },
    },
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
const { context: downloadContext, requests: downloadRequests, statusMessages } = recordingDownloadContext([
  { ok: true, json: async () => previewPayload() },
  fakeStreamResponse({ ...downloadPayload(), selection_name: "downloads", output_dir: "cache/saved_subsets/downloads" }),
]);
await requestLeafletSubset(downloadContext, true);
assert.deepEqual(statusMessages, [
  "Checking selected 1 m tiles...",
  "Choose an output folder to start the download/export.",
  "Downloading source tiles and building export...",
  "Saving downloaded files to the selected folder...",
  "Saved 0 source files and 0 GRD exports to downloads.",
]);
assert.equal(downloadContext.openDownloadFolderButton.hidden, false);
assert.equal(downloadContext.state.lastDownloadedOutputDir, "cache/saved_subsets/downloads");
assert.equal(
  JSON.parse(downloadRequests[1].options.body).selection_name,
  "downloads",
  "a blank job name should use the directory selected in the picker",
);
globalThis.window = originalWindow;

globalThis.window = {
  showDirectoryPicker: async () => fakeDirectoryHandle(),
};
const { context: progressContext } = recordingDownloadContext([
  { ok: true, json: async () => previewPayload() },
  fakeProgressStreamResponse(downloadPayload()),
]);
await requestLeafletSubset(progressContext, true);
assert.equal(progressContext.downloadProgress.value, 1);
assert.equal(progressContext.downloadProgress.max, 1);
assert.match(progressContext.document.tileList.innerHTML, /<s><code>geobasis-nrw\/dgm1\/tile-a<\/code><\/s>/);
globalThis.window = originalWindow;

globalThis.window = {
  showDirectoryPicker: async () => fakeDirectoryHandle(),
};
const failedEvents = [
  { type: "progress", provider: "geobasis-nrw", dataset: "dgm1", tile_id: "tile-a", current: 1, total: 1, success: false },
  { type: "error", message: "download stopped" },
];
const failedBytes = new TextEncoder().encode(failedEvents.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(""));
let failedConsumed = false;
const failedStream = {
  ok: true,
  body: { getReader: () => ({ read: async () => failedConsumed
    ? { done: true, value: undefined }
    : (failedConsumed = true, { done: false, value: failedBytes }) }) },
};
const { context: failedProgressContext } = recordingDownloadContext([
  { ok: true, json: async () => previewPayload() },
  failedStream,
]);
await requestLeafletSubset(failedProgressContext, true);
assert.equal(failedProgressContext.downloadProgress.value, 1);
assert.match(failedProgressContext.document.tileList.innerHTML, /<small>Failed<\/small>/);
globalThis.window = originalWindow;

globalThis.window = {
  showDirectoryPicker: async () => fakeDirectoryHandle(),
};
const { context: namedContext, requests: namedRequests } = recordingDownloadContext([
  { ok: true, json: async () => previewPayload() },
  fakeStreamResponse({ ...downloadPayload(), selection_name: "Customer_Site", output_dir: "cache/saved_subsets/Customer_Site" }),
]);
namedContext.jobNameInput.value = "Customer Site";
await requestLeafletSubset(namedContext, true);
assert.equal(
  JSON.parse(namedRequests[1].options.body).selection_name,
  "Customer_Site",
  "an explicit job name should override the selected directory name",
);
globalThis.window = originalWindow;

const autoOpenRequests = [];
globalThis.window = {
  showDirectoryPicker: async () => fakeDirectoryHandle(),
};
const autoOpenResponses = [
  { ok: true, json: async () => previewPayload() },
  fakeStreamResponse(downloadPayload()),
];
const { context: autoOpenContext } = recordingDownloadContext(autoOpenResponses);
autoOpenContext.openFolderAfterDownload.checked = true;
autoOpenContext.fetch = async (url) => {
  autoOpenRequests.push(url);
  if (url.endsWith("/api/v1/subsets/open-folder")) return { ok: true, json: async () => ({ status: "opened" }) };
  return autoOpenResponses.shift();
};
await requestLeafletSubset(autoOpenContext, true);
assert.equal(autoOpenContext.openDownloadFolderButton.hidden, false);
assert.equal(autoOpenRequests.some((url) => url.endsWith("/api/v1/subsets/open-folder")), true);
globalThis.window = originalWindow;

globalThis.window = {
  showDirectoryPicker: async () => fakeDirectoryHandle(),
};
const { context: pyramidContext, statusMessages: pyramidMessages } = recordingDownloadContext([
  { ok: true, json: async () => previewPayload() },
  fakeStreamResponse(downloadPayload()),
]);
pyramidContext.selectedExportProfile = () => "ellipse_mapinfo_tab_pyramids";
await requestLeafletSubset(pyramidContext, true);
assert.match(pyramidMessages.at(-1), /GeoTIFF \+ TAB \+ pyramid exports/);
globalThis.window = originalWindow;

const prompts = [];
globalThis.window = {
  showDirectoryPicker: async () => fakeDirectoryHandle(),
};
const { context: failedDownloadContext } = recordingDownloadContext([
  { ok: true, json: async () => previewPayload() },
  fakeStreamResponse(failedDownloadPayload()),
]);
failedDownloadContext.confirm = (message) => {
  prompts.push(message);
  return false;
};
await requestLeafletSubset(failedDownloadContext, true);
assert.match(prompts[0], /geobasis-nrw\/dgm1\/tile-b/);
assert.match(failedDownloadContext.downloadStatus.textContent, /Download stopped\. Missing 1 identified file/);
globalThis.window = originalWindow;

assert.match(
  missingDownloadPrompt([{ provider: "p", dataset: "d", tile_id: "t" }]),
  /Retry the missing files now/,
);

assert.deepEqual(
  datasetsForExport(["dgm1"], "ellipse_semantic_grc", "ldbv-by"),
  ["dgm1", "dom1", "bdom"],
  "the Bayern semantic bundle must include DGM, DOM, and LoD2/BDOM source data",
);
assert.deepEqual(
  datasetsForExport(["dgm1"], "ellipse_grd", "ldbv-by"),
  ["dgm1"],
);
assert.deepEqual(
  datasetsForExport(["dom1"], "ellipse_semantic_grc_1m", "ldbv-by"),
  ["dom1", "dgm1", "bdom"],
);
