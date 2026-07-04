import assert from "node:assert/strict";
import { createCorridorFlow } from "../src/corridor-flow.js";

function previewPayload() {
  return {
    provider: "auto",
    results: [{ provider: "lgl-bw", dataset: "dgm1", match_count: 1 }],
    total_estimated_source_bytes: 0,
    total_estimated_ellipse_bytes: 0,
  };
}

function downloadPayload() {
  return {
    provider: "auto",
    selection_name: "bw_test",
    output_dir: "cache/saved_subsets/bw_test",
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

function baseContext({ autoOpen }) {
  const requests = [];
  const responses = [previewPayload(), downloadPayload()];
  const context = {
    apiBaseUrl: "http://api.invalid",
    btnOpenDownloadFolder: { hidden: true },
    fetchWithTimeout: async (url) => {
      requests.push(url);
      if (url.endsWith("/api/v1/subsets/open-folder")) return { ok: true, json: async () => ({ status: "opened" }) };
      return { ok: true, json: async () => responses.shift() };
    },
    lookupStatus: { textContent: "" },
    openFolderAfterDownload: { checked: autoOpen },
    state: {
      apiReady: true,
      lastDownloadedOutputDir: null,
      siteA: { lat: 48.77, lon: 9.18 },
      siteB: { lat: 48.8, lon: 9.2 },
    },
  };
  return { context, requests };
}

const originalWindow = globalThis.window;
const originalDocument = globalThis.document;
globalThis.window = {
  confirm: () => true,
  showDirectoryPicker: async () => fakeDirectoryHandle(),
};
globalThis.document = {
  querySelector: () => ({ value: "ellipse_grd" }),
};

const manual = baseContext({ autoOpen: false });
await createCorridorFlow(manual.context).download();
assert.equal(manual.context.btnOpenDownloadFolder.hidden, false);
assert.equal(manual.requests.some((url) => url.endsWith("/api/v1/subsets/open-folder")), false);

await createCorridorFlow(manual.context).openLastDownloadedFolder();
assert.equal(manual.requests.some((url) => url.endsWith("/api/v1/subsets/open-folder")), true);
assert.match(manual.context.lookupStatus.textContent, /Opened output folder/);

const automatic = baseContext({ autoOpen: true });
await createCorridorFlow(automatic.context).download();
assert.equal(automatic.context.btnOpenDownloadFolder.hidden, false);
assert.equal(automatic.requests.some((url) => url.endsWith("/api/v1/subsets/open-folder")), true);
assert.match(automatic.context.lookupStatus.textContent, /Opened output folder/);

globalThis.window = originalWindow;
globalThis.document = originalDocument;
