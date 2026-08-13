import assert from "node:assert/strict";
import test from "node:test";
import { bindUniversalSearch, resetUniversalSearch, runUniversalSearch } from "../src/leaflet-universal-search.js";

test("universal search sends the selected type and renders results", async () => {
  const context = searchContext([{ label: "Site A", source: "network-site" }]);

  await runUniversalSearch(context);

  assert.match(context.requestedUrl, /q=01&kind=site/);
  assert.equal(context.results.children.length, 1);
  assert.equal(context.results.children[0].textContent, "Site A");
  assert.equal(context.status.textContent, "Choose a result.");
});

test("changing search type clears stale results and errors", () => {
  const context = searchContext([]);
  context.results.innerHTML = "old result";
  context.status.textContent = "Search failed.";

  resetUniversalSearch(context);

  assert.equal(context.results.innerHTML, "");
  assert.equal(context.status.textContent, "");
});

test("universal search exposes browser-side failure details", async () => {
  const context = searchContext([]);
  context.fetchFn = async () => { throw new TypeError("Failed to fetch"); };

  await runUniversalSearch(context);

  assert.equal(context.status.textContent, "Search failed: Failed to fetch");
});

test("typing two or more characters schedules a debounced search", () => {
  const scheduled = [];
  const context = searchContext([]);
  context.button = eventTarget();
  context.input = eventTarget({ value: "01" });
  context.typeSelect = eventTarget({ value: "site" });
  context.setTimeoutFn = (callback, delay) => { scheduled.push({ callback, delay }); return 1; };
  context.clearTimeoutFn = () => {};

  bindUniversalSearch(context);
  context.input.dispatch("input");

  assert.equal(scheduled.length, 1);
  assert.equal(scheduled[0].delay, 250);
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

function eventTarget(properties = {}) {
  const handlers = {};
  return {
    ...properties,
    addEventListener: (name, handler) => { handlers[name] = handler; },
    dispatch: (name, event = {}) => handlers[name]?.(event),
  };
}
