import assert from "node:assert/strict";
import { changePlanningMode } from "../src/leaflet-planning-mode.js";
import { planningSelectionMarkers, planningSelectionReadout } from "../src/leaflet-planning-state.js";

const liveState = {
  networkEnabled: true,
  activeSite: "B",
  searchSelectionActive: true,
  selectedNetworkLink: { name: "A-B" },
  siteA: { name: "A", lat: 53.51, lon: 10.28 },
  siteB: { name: "B", lat: 53.62, lon: 10.39 },
  point: { name: "Probe", lat: 53.72, lon: 10.41 },
};
const liveLayers = [{ id: "network" }, { id: "site-a" }, { id: "site-b" }];
const stateSnapshot = structuredClone(liveState);
const calls = [];
let currentVariant = "corridor";

changePlanningMode({
  next: "area",
  search: "?variant=corridor&build=probe",
  setVariant: (next) => { currentVariant = next; },
  heading: { textContent: "" },
  select: { value: "corridor" },
  measurement: { hidden: true },
  configure: () => calls.push("configure"),
  updateDrawingControls: (next) => calls.push(`draw:${next}`),
  history: { replaceState: (_state, _title, url) => calls.push(url) },
});

assert.equal(currentVariant, "area");
assert.deepEqual(liveState, stateSnapshot);
assert.equal(liveLayers[0].id, "network");
assert.deepEqual(calls, ["configure", "draw:area", "?variant=area&build=probe"]);

assert.deepEqual(planningSelectionMarkers(liveState).map((marker) => marker.label), ["A", "B", "P"]);
assert.match(planningSelectionReadout(liveState, "area", sampleText), /A: A/);
assert.match(planningSelectionReadout(liveState, "area", sampleText), /B: B/);
assert.match(planningSelectionReadout(liveState, "area", sampleText), /Point: Probe/);
assert.match(planningSelectionReadout(liveState, "area", sampleText), /Active: Site B/);

function sampleText(sample) {
  return sample?.name || "not set";
}
