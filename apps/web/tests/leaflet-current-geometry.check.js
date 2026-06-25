import assert from "node:assert/strict";
import { currentGeometryFrom, resolveCorridorBuffer } from "../src/leaflet-prototype-utils.js";

// currentGeometryFrom is the pure seam behind leaflet-prototype.js currentGeometry():
// it maps placement state + the active variant to the API geometry payload.

// 1. A manual draw geometry overrides everything, regardless of variant/sites.
const manual = { kind: "bbox", west: 1, south: 2, east: 3, north: 4 };
assert.equal(
  currentGeometryFrom({ manualGeometry: manual, siteA: { lat: 1, lon: 1 }, siteB: { lat: 2, lon: 2 } }, "corridor", "300"),
  manual,
);

// 2. Corridor with both sites -> corridor geometry; buffer from the raw input.
assert.deepEqual(
  currentGeometryFrom(
    { manualGeometry: null, siteA: { lat: 51.5, lon: 7.0 }, siteB: { lat: 51.6, lon: 7.2 } },
    "corridor",
    "300",
  ),
  { kind: "corridor", from_lon: 7.0, from_lat: 51.5, to_lon: 7.2, to_lat: 51.6, buffer_m: 300 },
);

// 3. Buffer resolution: default when missing/blank/non-numeric, clamped to 50..2000.
assert.equal(resolveCorridorBuffer(null), 150);
assert.equal(resolveCorridorBuffer(""), 150);
assert.equal(resolveCorridorBuffer("abc"), 150);
assert.equal(resolveCorridorBuffer("300"), 300);
assert.equal(resolveCorridorBuffer("10"), 50);
assert.equal(resolveCorridorBuffer("5000"), 2000);
// Via the corridor path with a missing buffer input -> default 150.
assert.equal(
  currentGeometryFrom({ siteA: { lat: 1, lon: 2 }, siteB: { lat: 3, lon: 4 } }, "corridor", null).buffer_m,
  150,
);

// 4. Corridor with a single site collapses to a point (siteA preferred).
assert.deepEqual(
  currentGeometryFrom({ siteA: { lat: 51.5, lon: 7.0 }, siteB: null }, "corridor", null),
  { kind: "point", lon: 7.0, lat: 51.5 },
);
assert.deepEqual(
  currentGeometryFrom({ siteA: null, siteB: { lat: 51.6, lon: 7.2 } }, "corridor", null),
  { kind: "point", lon: 7.2, lat: 51.6 },
);

// 5. Corridor with no sites -> null.
assert.equal(currentGeometryFrom({ siteA: null, siteB: null }, "corridor", null), null);

// 6. Area with a rectangle -> bbox from the layer bounds.
const rectangle = {
  getBounds: () => ({ getWest: () => 7.0, getSouth: () => 51.0, getEast: () => 7.2, getNorth: () => 51.2 }),
};
assert.deepEqual(
  currentGeometryFrom({ rectangle }, "area", null),
  { kind: "bbox", west: 7.0, south: 51.0, east: 7.2, north: 51.2 },
);

// 7. Area with no rectangle -> null.
assert.equal(currentGeometryFrom({ rectangle: null }, "area", null), null);

// 8. Point variant with a point -> point geometry.
assert.deepEqual(
  currentGeometryFrom({ point: { lat: 52.32, lon: 7.46 } }, "point", null),
  { kind: "point", lon: 7.46, lat: 52.32 },
);

// 9. Point variant with no point -> null.
assert.equal(currentGeometryFrom({ point: null }, "point", null), null);
