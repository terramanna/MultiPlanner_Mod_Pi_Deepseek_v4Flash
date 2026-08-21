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
  assert.match(renderPrototypeShell("corridor"), /id="measurementReadout"[^>]* hidden/);
  assert.doesNotMatch(renderPrototypeShell("area"), /id="measurementReadout"[^>]* hidden/);
  assert.match(renderPrototypeShell("point"), /id="measurementReadout"[^>]* hidden/);
});

test("export profiles are grouped in a categorized pick list", () => {
  const html = renderPrototypeShell("area");

  assert.match(html, /id="prototypeDownloadExportProfile"/);
  assert.match(html, /<optgroup label="Source files">/);
  assert.match(html, /<optgroup label="Operator intervention - MapInfo final conversion">/);
  assert.match(html, /<optgroup label="Automatic - Ellipse-ready \(no operator intervention\)">/);
  assert.match(html, /Operator MapInfo conversion required/);
  assert.match(html, /Automatic; ready for Ellipse/);
  assert.match(html, /Automatic formats complete conversion and are ready to import into Ellipse/);
  assert.match(html, /value="source_tiles"/);
  assert.match(html, /value="ellipse_grd" selected/);
  assert.match(html, /value="ellipse_mapinfo_tab_pyramids"/);
  assert.match(html, /value="ellipse_semantic_grc"/);
  assert.match(html, /building\/tree heights \(2 m, automatic\)/);
  assert.match(html, /building\/tree heights \(1 m comparison, automatic\)/);
  assert.match(html, />Download \+ export</);
});
