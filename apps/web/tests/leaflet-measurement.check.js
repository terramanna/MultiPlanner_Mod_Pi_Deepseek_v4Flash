import assert from "node:assert/strict";
import { safeMeasurementText } from "../src/leaflet-measurement.js";

assert.equal(safeMeasurementText(undefined, () => "unused"), "Drawing selection...");
assert.equal(
  safeMeasurementText({ kind: "empty rectangle" }, () => { throw new Error("Bounds are not valid"); }),
  "Drawing selection...",
);
assert.equal(safeMeasurementText({ kind: "rectangle" }, () => "10 m x 20 m"), "10 m x 20 m");
