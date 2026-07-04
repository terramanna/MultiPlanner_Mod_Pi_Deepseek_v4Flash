import assert from "node:assert/strict";
import { selectedLinkDetails } from "../src/leaflet-selected-link.js";

const details = selectedLinkDetails(
  {
    link_name: "HND_SITE_A_SITE_B",
    distance_m: 3790,
    site_a_name: "SITE_A",
    site_a_id: "S900001",
    site_a_label: "Actual Site A",
    site_a_structure: "Mast",
    site_a_type: "LTE",
    site_b_name: "SITE_B",
    site_b_id: "S900002",
    site_b_label: "Actual Site B",
    site_b_structure: "Dach",
    site_b_type: "LTE_POP",
  },
  { lat: 52, lon: 7 },
  { lat: 52.1, lon: 7.1 },
);

assert.equal(details[0], "HND_SITE_A_SITE_B");
assert.equal(details[1], "3.79 km A to B");
assert.match(details[2], /A: SITE_A \(S900001\) - Actual Site A · Mast · LTE/);
assert.match(details[3], /B: SITE_B \(S900002\) - Actual Site B · Dach · LTE_POP/);
