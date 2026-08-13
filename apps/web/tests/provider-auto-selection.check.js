import assert from "node:assert/strict";
import test from "node:test";
import { autoProviderForGeometry } from "../src/provider-auto-selection.js";

const west = coverageBox(6, 50, 8, 53);
const east = coverageBox(8, 50, 10, 53);
const features = { "provider-west": west, "provider-east": east };
const providers = ["auto", "provider-west", "provider-east"];

test("auto provider follows a point inside one provider coverage", () => {
  const geometry = { kind: "point", lat: 51, lon: 7 };
  assert.equal(autoProviderForGeometry(geometry, {}, features, providers), "provider-west");
});

test("auto provider follows a corridor contained within one coverage", () => {
  const state = { siteA: { lat: 51, lon: 6.5 }, siteB: { lat: 52, lon: 7.5 } };
  assert.equal(autoProviderForGeometry({ kind: "corridor" }, state, features, providers), "provider-west");
});

test("auto provider falls back to auto for a cross-provider selection", () => {
  const state = { siteA: { lat: 51, lon: 7 }, siteB: { lat: 51, lon: 9 } };
  assert.equal(autoProviderForGeometry({ kind: "corridor" }, state, features, providers), "auto");
});

test("auto provider waits for coverage and rejects unavailable providers", () => {
  const geometry = { kind: "point", lat: 51, lon: 7 };
  assert.equal(autoProviderForGeometry(geometry, {}, {}, providers), null);
  assert.equal(autoProviderForGeometry(geometry, {}, features, ["auto"]), "auto");
});

function coverageBox(west, south, east, north) {
  return {
    type: "Feature",
    geometry: {
      type: "Polygon",
      coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
    },
  };
}
