import assert from "node:assert/strict";
import test from "node:test";

import {
  bboxGeometry,
  circlePolygon,
  corridorGeometry,
  polygonGeometry,
} from "../src/cesium-geometry.js";


test("builds corridor and rectangle API geometries", () => {
  const first = { lon: 8, lat: 51 };
  const second = { lon: 7, lat: 52 };

  assert.deepEqual(corridorGeometry(first, second), {
    kind: "corridor", from_lon: 8, from_lat: 51,
    to_lon: 7, to_lat: 52, buffer_m: 75,
  });
  assert.deepEqual(bboxGeometry(first, second), {
    kind: "bbox", west: 7, south: 51, east: 8, north: 52,
  });
});


test("builds valid circle and polygon API geometries", () => {
  const circle = circlePolygon({ lon: 7, lat: 51 }, { lon: 7.01, lat: 51 }, 8);
  assert.equal(circle.kind, "polygon");
  assert.equal(circle.coordinates.length, 8);
  assert.ok(circle.coordinates.every((coordinate) => coordinate.length === 2));

  assert.equal(polygonGeometry([{ lon: 7, lat: 51 }, { lon: 8, lat: 51 }]), null);
  assert.deepEqual(
    polygonGeometry([{ lon: 7, lat: 51 }, { lon: 8, lat: 51 }, { lon: 8, lat: 52 }]),
    { kind: "polygon", coordinates: [[7, 51], [8, 51], [8, 52]] },
  );
});
