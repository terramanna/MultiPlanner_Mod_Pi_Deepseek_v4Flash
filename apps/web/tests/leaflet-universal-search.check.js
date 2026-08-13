import assert from "node:assert/strict";
import test from "node:test";
import { runUniversalSearch } from "../src/leaflet-universal-search.js";

test("universal search sends the selected type and renders results", async () => {
  const context = searchContext([{ label: "Site A", source: "network-site" }]);

  await runUniversalSearch(context);

  assert.match(context.requestedUrl, /q=01&kind=site/);
  assert.equal(context.results.children.length, 1);
  assert.equal(context.results.children[0].textContent, "Site A");
  assert.equal(context.status.textContent, "Choose a result.");
});

function searchContext(candidates) {
  const context = {
    apiBaseUrl: "http://api.invalid",
    input: { value: "01" },
    typeSelect: { value: "site" },
    status: { textContent: "" },
    results: fakeResults(),
    onCandidate: () => {},
  };
  context.fetchFn = async (url) => {
    context.requestedUrl = url;
    return { ok: true, json: async () => ({ candidates }) };
  };
  return context;
}

function fakeResults() {
  const children = [];
  return {
    children,
    innerHTML: "",
    ownerDocument: {
      createElement: () => ({ addEventListener: () => {}, className: "", textContent: "" }),
    },
    appendChild: (child) => children.push(child),
  };
}
