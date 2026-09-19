import assert from "node:assert/strict";
import { buildSelectionName } from "../src/utils.js";

// buildSelectionName generates the default download/file name. A typed job name
// always wins and is slugged; otherwise the name is built from the geometry kind
// plus optional provider-region tokens detected from coverage features.

function jobInput(value = "") {
  return { value };
}

function constMap(meters) {
  return { distance: () => meters };
}

// Rectangle width/height come from two distance() calls: width keeps latitude
// fixed (longitude differs), height keeps longitude fixed (latitude differs).
function bboxMap(widthM, heightM) {
  return {
    distance: ([latA, lonA], [latB, lonB]) => {
      if (latA === latB && lonA !== lonB) return widthM;
      if (lonA === lonB && latA !== latB) return heightM;
      return 0;
    },
  };
}

function noCoverage(extra = {}) {
  return { coverageFeatures: {}, ...extra };
}

// A coverage polygon covering roughly lat 50-53, lon 6-8 mapped to a state code,
// so detectProviderTokens yields a region token for points inside it.
function coverageBox(stateCode) {
  const feature = {
    type: "Feature",
    geometry: { type: "Polygon", coordinates: [[[6, 50], [8, 50], [8, 53], [6, 53], [6, 50]]] },
  };
  return {
    state: { coverageFeatures: { "prov-x": feature } },
    providerCoverage: { "prov-x": { stateCode } },
  };
}

const noProviders = {};

// 1. Typed name wins and is slugged (spaces/punctuation collapse to underscores).
assert.equal(
  buildSelectionName({ kind: "point", lat: 1, lon: 1 }, noCoverage(), constMap(0), jobInput("  Customer Site 7  "), noProviders),
  "Customer_Site_7",
);

// 2. Corridor: length-km + total-width tokens; no coverage -> no region.
assert.equal(
  buildSelectionName(
    { kind: "corridor", buffer_m: 150 },
    noCoverage({ siteA: { lat: 51.5, lon: 7.0 }, siteB: { lat: 51.6, lon: 7.2 } }),
    constMap(5000),
    jobInput(),
    noProviders,
  ),
  "siteA_siteB_link_5km_300m_corridor_1m_merge",
);

// 2b. Corridor with a detected region token from coverage.
{
  const cov = coverageBox("NW");
  assert.equal(
    buildSelectionName(
      { kind: "corridor", buffer_m: 150 },
      { ...cov.state, siteA: { lat: 51.5, lon: 7.0 }, siteB: { lat: 51.6, lon: 7.2 } },
      constMap(5000),
      jobInput(),
      cov.providerCoverage,
    ),
    "siteA_siteB_link_5km_300m_corridor_NW_1m_merge",
  );
}

// 3. Point: coordinate token (decimal points slugged to underscores); no region.
assert.equal(
  buildSelectionName({ kind: "point", lat: 52.32, lon: 7.46 }, noCoverage(), constMap(0), jobInput(), noProviders),
  "point_n52_3200_e7_4600_1m_merge",
);

// 3b. Point with a detected region token from coverage.
{
  const cov = coverageBox("NW");
  assert.equal(
    buildSelectionName({ kind: "point", lat: 52.32, lon: 7.46 }, cov.state, constMap(0), jobInput(), cov.providerCoverage),
    "point_n52_3200_e7_4600_NW_1m_merge",
  );
}

// 4. Bbox: rectangle width/height dimension tokens.
assert.equal(
  buildSelectionName(
    { kind: "bbox", north: 52, south: 51.9, east: 7.1, west: 7.0 },
    noCoverage(),
    bboxMap(2000, 800),
    jobInput(),
    noProviders,
  ),
  "rectangle_2km_800m_1m_merge",
);

// 5. Polygon with name_hint: hint + region + _1m_merge.
assert.equal(
  buildSelectionName(
    { kind: "polygon", name_hint: "circle_2km_diameter", coordinates: [[7, 51], [7.1, 51], [7.1, 51.1]] },
    noCoverage(),
    constMap(0),
    jobInput(),
    noProviders,
  ),
  "circle_2km_diameter_1m_merge",
);

// 6. Polygon without hint: estimated-diameter token.
assert.equal(
  buildSelectionName(
    { kind: "polygon", coordinates: [[7, 51], [7.1, 51], [7.1, 51.1]] },
    noCoverage(),
    constMap(3000),
    jobInput(),
    noProviders,
  ),
  "polygon_3km_diameter_1m_merge",
);

// 7. Unknown kind: kind + _1m_merge fallback.
assert.equal(
  buildSelectionName({ kind: "site" }, noCoverage(), constMap(0), jobInput(), noProviders),
  "site_1m_merge",
);

// 7b. Corridor geometry missing a site falls through to the kind fallback.
assert.equal(
  buildSelectionName({ kind: "corridor" }, noCoverage(), constMap(0), jobInput(), noProviders),
  "corridor_1m_merge",
);
