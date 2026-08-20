import assert from "node:assert/strict";
import {
  DEFAULT_LEAFLET_VIEW,
  leafletViewFromSearch,
  searchWithPlanningModeViewport,
} from "../src/leaflet-map-viewport.js";

assert.deepEqual(leafletViewFromSearch("?variant=area"), DEFAULT_LEAFLET_VIEW);
assert.deepEqual(
  leafletViewFromSearch("?variant=point&mapLat=53.722818&mapLon=10.415897&mapZoom=15"),
  { lat: 53.722818, lon: 10.415897, zoom: 15 },
);
assert.deepEqual(
  leafletViewFromSearch("?mapLat=999&mapLon=10.4&mapZoom=15"),
  DEFAULT_LEAFLET_VIEW,
);

const nextSearch = searchWithPlanningModeViewport(
  "?variant=corridor&build=probe",
  "area",
  { lat: 53.7228178, lng: 10.4158966 },
  14,
);
const params = new URLSearchParams(nextSearch);

assert.equal(params.get("variant"), "area");
assert.equal(params.get("build"), "probe");
assert.equal(params.get("mapLat"), "53.722818");
assert.equal(params.get("mapLon"), "10.415897");
assert.equal(params.get("mapZoom"), "14");
