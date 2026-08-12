import assert from "node:assert/strict";
import {
  buildPathProfileRequest,
  fresnelRadiusMeters,
  gigahertzToMegahertz,
  linkDistanceMeters,
  profileSourceOptions,
} from "../src/link-profile-window.js";

const onlyDgm = profileSourceOptions(["dgm1"]);
assert.equal(onlyDgm.find((option) => option.value === "dgm1").available, true);
assert.equal(onlyDgm.find((option) => option.value === "dom1").available, false);
assert.equal(onlyDgm.find((option) => option.value === "dgm1_dom1").available, false);

const dgmAndDom = profileSourceOptions(["dgm1", "dom1"]);
assert.equal(dgmAndDom.find((option) => option.value === "dgm1_dom1").available, true);

const nearOneKm = linkDistanceMeters(
  { lat: 52.0, lon: 7.0 },
  { lat: 52.0, lon: 7.0146 },
);
assert.ok(nearOneKm > 990);
assert.ok(nearOneKm < 1010);

const firstZoneRadius = fresnelRadiusMeters(1000, 6000, 1, 0.5);
const secondZoneRadius = fresnelRadiusMeters(1000, 6000, 2, 0.5);
assert.ok(firstZoneRadius > 3.4);
assert.ok(firstZoneRadius < 3.7);
assert.ok(secondZoneRadius > firstZoneRadius);

assert.equal(gigahertzToMegahertz(6), 6000);
assert.equal(gigahertzToMegahertz(18), 18000);

const request = buildPathProfileRequest(
  {
    siteA: { lon: 7, lat: 52, height: 100 },
    siteB: { lon: 7.1, lat: 52.1, height: 125 },
  },
  { source: "dom1", antennaHeightM: 35, frequencyMhz: 18000, fresnelZone: 2 },
);
assert.equal(request.provider, "auto");
assert.equal(request.source, "dom1");
assert.equal(request.site_a.height_m, 100);
assert.equal(request.antenna_height_m, 35);
assert.equal(request.frequency_mhz, 18000);
assert.equal(request.fresnel_zone, 2);
