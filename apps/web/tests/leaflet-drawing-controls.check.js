import assert from "node:assert/strict";
import test from "node:test";
import { addAreaDrawingControls } from "../src/leaflet-drawing-controls.js";

test("drawing controls are not installed for corridor or point modes", () => {
  const map = fakeMap();
  assert.equal(addAreaDrawingControls(map, "corridor"), false);
  assert.equal(addAreaDrawingControls(map, "point"), false);
  assert.equal(map.calls.length, 0);
});

test("area mode installs only area drawing controls", () => {
  const map = fakeMap();
  assert.equal(addAreaDrawingControls(map, "area"), true);
  assert.equal(map.calls.length, 1);
  assert.equal(map.calls[0].drawRectangle, true);
  assert.equal(map.calls[0].drawPolygon, true);
  assert.equal(map.calls[0].drawCircle, true);
  assert.equal(map.calls[0].drawMarker, false);
});

function fakeMap() {
  const calls = [];
  return { calls, pm: { addControls: (options) => calls.push(options) } };
}
