import assert from "node:assert/strict";
import { buildSearchPlacesUrl } from "../src/leaflet-search-request.js";

const url = buildSearchPlacesUrl("http://api.invalid", "Bonn", "site", {
  getWest: () => 7.0123456,
  getSouth: () => 50.7012345,
  getEast: () => 7.2123456,
  getNorth: () => 50.9012345,
});

assert.equal(
  url,
  "http://api.invalid/api/v1/search/places?q=Bonn&kind=site&west=7.012346&south=50.701234&east=7.212346&north=50.901235",
);

assert.equal(
  buildSearchPlacesUrl("http://api.invalid", "Bonn", "all"),
  "http://api.invalid/api/v1/search/places?q=Bonn&kind=all",
);
