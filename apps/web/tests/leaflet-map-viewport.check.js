import assert from "node:assert/strict";
import {
  DEFAULT_LEAFLET_VIEW,
  leafletViewFromSearch,
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
