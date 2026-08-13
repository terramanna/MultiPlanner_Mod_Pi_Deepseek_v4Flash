import assert from "node:assert/strict";
import test from "node:test";
import { renderPrototypeShell } from "../src/leaflet-prototype-shell.js";

test("planner mode selector is rendered in the Leaflet panel", () => {
  const html = renderPrototypeShell("corridor");

  assert.match(html, /<label for="variantSelect">Planning mode<\/label>/);
  assert.match(html, /value="corridor" selected/);
  assert.doesNotMatch(html, /prototype-switcher|Open Cesium comparison/);
});

test("universal search is rendered over the map rather than in the side panel", () => {
  const html = renderPrototypeShell("corridor");
  const panelEnd = html.indexOf("</aside>");
  const searchStart = html.indexOf("prototype-universal-search");

  assert.ok(searchStart > panelEnd);
  assert.match(html, /Search sites, links, places, or coordinates/);
  assert.match(html, /<option value="all">All<\/option>/);
  assert.match(html, /<option value="site">Sites<\/option>/);
  assert.match(html, /<option value="link">Links<\/option>/);
  assert.match(html, /<option value="place">Places<\/option>/);
  assert.doesNotMatch(html, /Use the layer button/);
});

test("drawing guidance is limited to area mode", () => {
  assert.doesNotMatch(renderPrototypeShell("corridor"), /measurementReadout/);
  assert.match(renderPrototypeShell("area"), /id="measurementReadout"/);
  assert.doesNotMatch(renderPrototypeShell("point"), /measurementReadout/);
});

test("separate Bayern building and tree GRC export is selectable", () => {
  const html = renderPrototypeShell("area");

  assert.match(html, /value="ellipse_semantic_grc"/);
  assert.match(html, /Bayern DGM \+ DOM \+ buildings \+ trees GRC/);
  assert.match(html, />Download \+ export</);
});
