import assert from "node:assert/strict";
import test from "node:test";

import { renderCesiumShell } from "../src/cesium-shell.js";


test("Cesium shell preserves planner controls and local terrain label", () => {
  const html = renderCesiumShell(false);

  for (const id of [
    "cesiumContainer", "btnSiteA", "btnSiteB", "btnSearch", "btnLocate",
    "btnDownload", "btnOpenDownloadFolder", "lookupStatus",
  ]) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(html, /fast local/);
});


test("Cesium shell reports world terrain mode", () => {
  assert.match(renderCesiumShell(true), /world terrain/);
});
