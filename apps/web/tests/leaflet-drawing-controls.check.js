import assert from "node:assert/strict";
import test from "node:test";
import { addAreaDrawingControls, updateAreaDrawingControls } from "../src/leaflet-drawing-controls.js";

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

test("planning mode changes replace drawing controls without touching map layers", () => {
  const map = fakeMap();
  map.layers = [{ id: "selected-link" }, { id: "network" }];
  map.activeShape = "Rectangle";

  updateAreaDrawingControls(map, "area");
  updateAreaDrawingControls(map, "point");

  assert.equal(map.removedControls, 2);
  assert.deepEqual(map.disabledShapes, ["Rectangle"]);
  assert.deepEqual(map.layers, [{ id: "selected-link" }, { id: "network" }]);
});

function fakeMap() {
  const calls = [];
  const map = {
    calls,
    disabledShapes: [],
    removedControls: 0,
    pm: {},
  };
  map.pm.addControls = (options) => calls.push(options);
  map.pm.removeControls = () => { map.removedControls += 1; };
  map.pm.Draw = { getActiveShape: () => map.activeShape };
  map.pm.disableDraw = (shape) => {
    map.disabledShapes.push(shape);
    map.activeShape = null;
  };
  return map;
}
