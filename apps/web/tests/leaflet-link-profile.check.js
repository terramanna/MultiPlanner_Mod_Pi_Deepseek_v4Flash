import assert from "node:assert/strict";
import { buildLeafletPathProfileRequest, gigahertzToMegahertz, resolveProfileProvider } from "../src/leaflet-link-profile.js";

assert.equal(gigahertzToMegahertz(6), 6000);
assert.equal(gigahertzToMegahertz(13), 13000);

const request = buildLeafletPathProfileRequest(
  {
    siteA: { lat: 52.0, lon: 7.0 },
    siteB: { lat: 52.1, lon: 7.1, height: 112 },
  },
  { source: "dgm1_dom1", antennaAHeightM: 28, antennaBHeightM: 42, frequencyMhz: 13000, fresnelZone: 2 },
  "auto",
);

assert.equal(request.provider, "auto");
assert.equal(request.source, "dgm1_dom1");
assert.deepEqual(request.site_a, { lat: 52.0, lon: 7.0, height_m: 0 });
assert.deepEqual(request.site_b, { lat: 52.1, lon: 7.1, height_m: 112 });
assert.equal(request.antenna_a_height_m, 28);
assert.equal(request.antenna_b_height_m, 42);
assert.equal(request.frequency_mhz, 13000);
assert.equal(request.fresnel_zone, 2);
assert.equal(request.sample_count, 25);

const denseRequest = buildLeafletPathProfileRequest(
  {
    siteA: { lat: 52.0, lon: 7.0 },
    siteB: { lat: 52.1, lon: 7.1 },
  },
  { source: "dom1", antennaHeightM: 30, frequencyMhz: 26000, fresnelZone: 1, sampleCount: 51 },
  "auto",
);

assert.equal(denseRequest.sample_count, 51);

assert.equal(
  resolveProfileProvider({
    siteA: { lat: 48.7, lon: 9.1 },
    siteB: { lat: 48.8, lon: 9.2 },
  }, "auto"),
  "lgl-bw",
);
