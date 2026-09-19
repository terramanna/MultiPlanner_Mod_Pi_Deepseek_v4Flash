// PROTOTYPE: compares a 2D Leaflet subset-selection workflow with the Cesium shell.
// Variants: corridor, area, and point. Select with ?variant=corridor|area|point.
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@geoman-io/leaflet-geoman-free";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import "./leaflet-prototype.css";
import { retryUntilReady } from "./bootstrap-retry.js";
import { createPointProbe } from "./leaflet-point-probe.js";
import { createNetworkOverlay } from "./leaflet-network-overlay.js";
import { createLeafletLinkProfile } from "./leaflet-link-profile.js";
import { createLod2Layer } from "./leaflet-bb-lod2.js";
import { leafletViewFromSearch } from "./leaflet-map-viewport.js";
import { safeMeasurementText } from "./leaflet-measurement.js";
import { changePlanningMode } from "./leaflet-planning-mode.js";
import { planningSelectionMarkers, planningSelectionReadout } from "./leaflet-planning-state.js";
import { clearLeafletSelection } from "./leaflet-selection.js";
import { requestLeafletSubset } from "./leaflet-subset-request.js";
import { bindPersistedInput } from "./persisted-input.js";
import { renderPrototypeShell } from "./leaflet-prototype-shell.js";
import { createCoverageOverlay } from "./leaflet-coverage-overlay.js";
import { updateAreaDrawingControls } from "./leaflet-drawing-controls.js";
import { addLeafletLayerControl } from "./leaflet-layer-control.js";
import { applySearchCandidateToState } from "./leaflet-search-results.js";
import { bindUniversalSearch } from "./leaflet-universal-search.js";
import { openSelectedLinkPopup } from "./leaflet-selected-link.js";
import { autoProviderForGeometry } from "./provider-auto-selection.js";
import { applyProviderSelection, sortProviders } from "./provider-selection.js";
import {
  currentGeometryFrom,
  flattenLatLngs,
  formatArea,
  formatMeters,
  geometryFromLayer,
  polygonAreaM2,
  renderDatasetChoices,
<<<<<<< HEAD
} from "./utils.js";
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? window.location.origin).trim();
const providerCoverage = {
  "lgln-ni": { stateCode: "NI", color: "#3b82f6", label: "Niedersachsen LGLN" },
  "geobasis-nrw": { stateCode: "NW", color: "#f97316", label: "NRW Geobasis" },
  "geosn-sn": { stateCode: "SN", color: "#16a34a", label: "Saxony GeoSN" },
  "hvbg-he": { stateCode: "HE", color: "#dc2626", label: "Hessen HVBG" },
  "lvermgeo-st": { stateCode: "ST", color: "#7c3aed", label: "Saxony-Anhalt LVermGeo" },
  "geobasis-bb": { stateCode: "BB", color: "#eab308", label: "Brandenburg Geobasis" },
  "lgl-bw": { stateCode: "BW", color: "#0f766e", label: "Baden-Wuerttemberg LGL" },
  "ldbv-by": { stateCode: "BY", color: "#2563eb", label: "Bayern LDBV" },
  "lgv-hh": { stateCode: "HH", color: "#0891b2", label: "Hamburg LGV", hideKmThreshold: 2 },
  "lvermgeo-sh": { stateCode: "SH", color: "#14b8a6", label: "Schleswig-Holstein LVermGeo" },
  "laiv-mv": { stateCode: "MV", color: "#a21caf", label: "Mecklenburg-Vorpommern LAiV" },
  "lginf-hb": { stateCode: "HB", color: "#65a30d", label: "Bremen Landesamt Geoinformation", hideKmThreshold: 2 },
  "gdi-be": { stateCode: "BE", color: "#4338ca", label: "Berlin GDI", hideKmThreshold: 2 },
  "tlbg-th": { stateCode: "TH", color: "#b45309", label: "Thüringen TLBG" },
  "lvgl-sl": { stateCode: "SL", color: "#e11d48", label: "Saarland LVGL" },
  "lvermgeo-rp": { stateCode: "RP", color: "#7c2d12", label: "Rheinland-Pfalz LVermGeo" },
};
const variants = ["corridor", "area", "point"];
const params = new URLSearchParams(window.location.search);
let variant = variants.includes(params.get("variant")) ? params.get("variant") : "corridor";
const app = document.getElementById("app");

app.innerHTML = renderPrototypeShell(variant);

const initialMapView = leafletViewFromSearch(window.location.search);
const map = L.map("leafletMap", { zoomControl: true }).setView(
  [initialMapView.lat, initialMapView.lon], initialMapView.zoom
);
map.getContainer().classList.add("is-site-placement");
const bbLod2Layer = createLod2Layer(map);
addLeafletLayerControl(L, map, bbLod2Layer);
L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);
const zoomLevelControl = L.control({ position: "bottomleft" });
zoomLevelControl.onAdd = function (m) {
  const div = L.DomUtil.create("div");
  div.style.cssText = "background:rgba(255,255,255,0.85);padding:3px 8px;border-radius:3px;font:12px/1.5 monospace;box-shadow:0 1px 4px rgba(0,0,0,.3)";
  const update = () => { div.textContent = `Zoom ${m.getZoom()}`; };
  update();
  m.on("zoom", update);
  return div;
};
zoomLevelControl.addTo(map);
updateAreaDrawingControls(map, variant);

const state = {
  activeSite: null,
  provider: "auto",
  providerAutoDetect: true,
  providers: [],
  providerSortDirection: "asc",
  searchSelectionActive: false,
  apiReady: false,
  siteA: null,
  siteB: null,
  areaStart: null,
  point: null,
  markers: [],
  line: null,
  rectangle: null,
  manualLayer: null,
  manualGeometry: null,
  isDrawing: false,
  coverageLayers: {},
  coverageFeatures: {},
  lastDownloadedOutputDir: null,
  selectedNetworkLink: null
};

const bootstrapAbortController = new AbortController();
const providerSelectionMonitor = window.setInterval(monitorProviderSelection, 250);

const placementActions = document.getElementById("placementActions");
const planningModeHeading = document.getElementById("planningModeHeading");
const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const searchTypeSelect = document.getElementById("searchTypeSelect");
const searchStatus = document.getElementById("searchStatus");
const searchResults = document.getElementById("searchResults");
const selectionReadout = document.getElementById("selectionReadout");
const downloadStatus = document.getElementById("downloadStatus");
const downloadProgress = document.getElementById("downloadProgress");
const tileList = document.getElementById("tileList");
const providerSelect = document.getElementById("providerSelect");
const providerSortSelect = document.getElementById("providerSortSelect");
const providerModeStatus = document.getElementById("providerModeStatus");
const jobNameInput = document.getElementById("jobNameInput");
const measurementReadout = document.getElementById("measurementReadout");
const coverageToggle = document.getElementById("coverageToggle");
const openFolderAfterDownload = document.getElementById("openFolderAfterDownload");
const openDownloadFolderButton = document.getElementById("btnOpenDownloadFolder");
bindPersistedInput(searchInput, "multiplanner.leaflet.searchInput");
bindUniversalSearch({
  apiBaseUrl: window.location.origin, button: searchButton, fetchFn: (url, options) => window.fetch(url, options), input: searchInput,
  onCandidate: chooseCandidate, results: searchResults, status: searchStatus,
  typeSelect: searchTypeSelect,
});
const { loadProviderCoverage, updateCoverageOverlay } = createCoverageOverlay(
  map, state, providerCoverage, coverageToggle, downloadStatus
);

configureVariant();
refreshReadout();
bootstrapApi();
loadProviderCoverage().then(refreshReadout);
const pointProbe = createPointProbe(
  map, apiBaseUrl,
  () => state.provider,
  () => document.getElementById("probeDataset")?.value ?? "multi"
);
const linkProfile = createLeafletLinkProfile({ L, map, apiBaseUrl, provider: () => state.provider, fetchFn: fetch });
const networkOverlay = createNetworkOverlay(map, apiBaseUrl, {
  onSiteA: (p) => { state.activeSite = "A"; placeSample({ lat: p.lat, lon: p.lon }, false); },
  onSiteB: (p) => { state.activeSite = "B"; placeSample({ lat: p.lat, lon: p.lon }, false); },
  onCorridor: (p) => { state.siteA = { lat: p.lat_a, lon: p.lon_a }; state.siteB = { lat: p.lat_b, lon: p.lon_b }; redrawGeometry(); refreshReadout(); },
  onProfile: (p, latlng) => linkProfile.openNetwork(p, latlng),
});

if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    bootstrapAbortController.abort();
    window.clearInterval(providerSelectionMonitor);
  });
}

window.addEventListener(
  "beforeunload",
  () => {
    bootstrapAbortController.abort();
  },
  { once: true }
);

map.on("click", (event) => {
  if (state.isDrawing) return;
  if (pointProbe.isActive()) { pointProbe.probe(event.latlng); return; }
  if (state.searchSelectionActive) { releaseCurrentSelection(); return; }
  placeFromMap(event.latlng);
});
map.on("pm:drawstart", (event) => {
  state.isDrawing = true;
  map.getContainer().classList.remove("is-site-placement");
  watchMeasurement(event.workingLayer);
});
map.on("pm:drawend", () => {
  state.isDrawing = false;
  map.getContainer().classList.add("is-site-placement");
});
map.on("pm:create", (event) => setManualGeometry(event.layer));
document.getElementById("locateButton").addEventListener("click", () => requestLeafletSubset(subsetRequestContext(), false));
document.getElementById("downloadButton").addEventListener("click", () => requestLeafletSubset(subsetRequestContext(), true));
document.getElementById("clearButton").addEventListener("click", releaseCurrentSelection);
openDownloadFolderButton.addEventListener("click", openLastDownloadedFolder);
document.getElementById("variantSelect").addEventListener("change", (event) => switchVariant(event.target.value));
providerSelect.addEventListener("input", handleProviderSelection);
providerSelect.addEventListener("change", handleProviderSelection);
providerSortSelect.addEventListener("input", handleProviderSortChange);
coverageToggle.addEventListener("change", updateCoverageOverlay);
const networkToggle = document.getElementById("networkToggle");
const networkOtherToggle = document.getElementById("networkOtherToggle");
const networkFilterWrap = document.getElementById("networkFilterWrap");
const networkFilter = document.getElementById("networkFilter");
function updateNetworkFilterVisibility() {
  networkFilterWrap.hidden = !networkToggle.checked && !networkOtherToggle.checked;
}
networkToggle.addEventListener("change", async () => {
  updateNetworkFilterVisibility();
  if (networkToggle.checked) { await networkOverlay.enable("primary_nominal"); } else { networkOverlay.disable("primary_nominal"); }
});
networkOtherToggle.addEventListener("change", async () => {
  updateNetworkFilterVisibility();
  if (networkOtherToggle.checked) { await networkOverlay.enable("other"); } else { networkOverlay.disable("other"); }
});
networkFilter.addEventListener("input", () => networkOverlay.filter(networkFilter.value));
const probeEnable = document.getElementById("probeEnable");
const probeSampleNow = document.getElementById("probeSampleNow");
probeEnable.addEventListener("change", () => {
  const active = pointProbe.toggle();
  const hover = document.getElementById("probeModeHover").checked;
  document.getElementById("probeStatus").textContent = active ? (hover ? "Move cursor to probe." : "Click map to probe.") : "";
  probeSampleNow.disabled = !active;
});
document.querySelectorAll('input[name="protoProbeMode"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    const hover = document.getElementById("probeModeHover").checked;
    pointProbe.setHoverMode(hover);
    if (pointProbe.isActive()) document.getElementById("probeStatus").textContent = hover ? "Move cursor to probe." : "Click map to probe.";
  });
});
probeSampleNow.addEventListener("click", () => pointProbe.sampleNow());

function monitorProviderSelection() {
  if (state.providers.length && providerSelect.value !== state.provider) {
    syncProviderSelection(true);
  }
}

function configureVariant() {
  const help = document.getElementById("modeHelp");
  if (variant === "corridor") {
    help.textContent = "Place one site to fetch its tile coverage, or place Site A and Site B to fetch a buffered corridor between them.";
    placementActions.innerHTML = '<button id="siteAButton" class="secondary">Place Site A</button><button id="siteBButton" class="secondary">Place Site B</button><div id="sitePlacementStatus" class="placement-state"></div><label for="bufferInput" style="margin-top:8px;display:block">Corridor buffer (m each side)</label><input id="bufferInput" type="number" min="50" max="2000" step="50" value="150" style="width:100%" />';
    document.getElementById("siteAButton").addEventListener("click", () => toggleActiveSite("A"));
    document.getElementById("siteBButton").addEventListener("click", () => toggleActiveSite("B"));
  } else if (variant === "area") {
    help.textContent = "Click two opposite corners to define the exact rectangular subset area.";
    placementActions.innerHTML = '<button id="areaButton">Start rectangle</button>';
    document.getElementById("areaButton").addEventListener("click", () => { state.areaStart = null; downloadStatus.textContent = "Click the first rectangle corner."; });
  } else {
    help.textContent = "Click one location to download the tile coverage around that point.";
    placementActions.innerHTML = '<button id="pointButton">Set point</button>';
    document.getElementById("pointButton").addEventListener("click", () => { state.point = null; refreshReadout(); });
  }
}

function placeFromMap(latlng) {
  if (variant === "corridor" && !state.activeSite) {
    downloadStatus.textContent = "Select Place Site A or Place Site B before clicking the map.";
    return;
  }
  placeSample({ lat: latlng.lat, lon: latlng.lng }, false);
}

function placeSample(sample, panTo) {
  state.searchSelectionActive = false;
  state.selectedNetworkLink = null;
  if (variant === "corridor") {
    if (state.activeSite === "A") state.siteA = sample;
    if (state.activeSite === "B") state.siteB = sample;
  } else if (variant === "area") {
    if (!state.areaStart) {
      state.areaStart = sample;
      downloadStatus.textContent = "Click the opposite rectangle corner.";
    } else {
      drawArea(state.areaStart, sample);
      state.areaStart = null;
    }
  } else {
    state.point = sample;
  }
  redrawGeometry();
  refreshReadout();
  if (panTo) map.setView([sample.lat, sample.lon], 14, { animate: false });
}

function redrawGeometry() {
  for (const marker of state.markers) map.removeLayer(marker);
  state.markers = [];
  if (state.line) map.removeLayer(state.line);
  state.line = null;
  for (const marker of planningSelectionMarkers(state)) {
    state.markers.push(circle(marker.sample, marker.color, marker.label));
  }
  if (state.siteA && state.siteB) state.line = L.polyline([[state.siteA.lat, state.siteA.lon], [state.siteB.lat, state.siteB.lon]], { color: "#7dff8c", weight: 4 }).on("click", openSiteLinkActions).addTo(map);
}

function circle(sample, color, label) {
  const options = { radius: 8, color, fillColor: color, fillOpacity: 0.9, weight: 2, bubblingMouseEvents: false };
  return L.circleMarker([sample.lat, sample.lon], options).bindTooltip(label, { permanent: true, direction: "top" }).addTo(map);
}

function drawArea(first, second) {
  if (state.rectangle) map.removeLayer(state.rectangle);
  state.rectangle = L.rectangle([[first.lat, first.lon], [second.lat, second.lon]], { color: "#ffdd57", weight: 3, fillOpacity: 0.12 }).addTo(map);
  map.fitBounds(state.rectangle.getBounds(), { padding: [32, 32], animate: false });
}

function currentGeometry() {
  const bufferInput = document.getElementById("bufferInput");
  return currentGeometryFrom(state, variant, bufferInput ? bufferInput.value : null);
}

function refreshReadout() {
  autoSelectProvider();
  selectionReadout.textContent = planningSelectionReadout(state, variant, sampleText);
  updateSiteToggleButtons();
}

function toggleActiveSite(site) {
  state.searchSelectionActive = false;
  state.activeSite = state.activeSite === site ? null : site;
  refreshReadout();
}

function updateSiteToggleButtons() {
  const placementStatus = document.getElementById("sitePlacementStatus");
  if (placementStatus) placementStatus.textContent = state.activeSite ? `Site ${state.activeSite} armed - click the map to place it.` : "No site armed - select Site A or Site B.";
  for (const site of ["A", "B"]) {
    document.getElementById(`site${site}Button`)?.classList.toggle("is-active", state.activeSite === site);
  }
}

function sampleText(sample) {
  if (!sample) return "not set";
  const identity = [sample.name, sample.id && `(${sample.id})`].filter(Boolean).join(" ");
  return `${identity ? `${identity} - ` : ""}${sample.lat.toFixed(6)}, ${sample.lon.toFixed(6)}`;
}

async function bootstrapApi() {
  searchStatus.textContent = "Waiting for backend";
  await retryUntilReady(loadProviderBootstrap, {
    signal: bootstrapAbortController.signal,
    delayMs: 1000,
    onRetry: () => {
      if (!state.apiReady) {
        searchStatus.textContent = "Waiting for backend";
      }
    },
  });
}

async function loadProviderBootstrap() {
  const [healthResponse, providersResponse] = await Promise.all([
    fetch(`${apiBaseUrl}/healthz`),
    fetch(`${apiBaseUrl}/api/v1/providers`)
  ]);
  if (!healthResponse.ok || !providersResponse.ok) throw new Error("API unavailable");
  const payload = await providersResponse.json();
  state.providers = payload.providers || [];
  populateProviderSelect(state.providers, state.providerSortDirection);
  state.apiReady = true;
  searchStatus.textContent = "API ready";
}

function populateProviderSelect(providers, sortDirection) {
  const sortedProviders = sortProviders(providers, sortDirection);
  providerSelect.innerHTML = "";
  for (const provider of sortedProviders) {
    const option = document.createElement("option");
    option.value = provider.name;
    option.textContent = provider.label;
    option.selected = provider.name === state.provider;
    providerSelect.appendChild(option);
  }
  if (!sortedProviders.some((provider) => provider.name === state.provider)) {
    state.provider = sortedProviders[0]?.name || "";
  }
  syncProviderSelection(false);
}

function handleProviderSelection() {
  if (!state.providers.length) return;
  state.providerAutoDetect = providerSelect.value === "auto";
  syncProviderSelection(true);
  refreshReadout();
}

function handleProviderSortChange() {
  state.providerSortDirection = providerSortSelect.value === "desc" ? "desc" : "asc";
  populateProviderSelect(state.providers, state.providerSortDirection);
}

function syncProviderSelection(clearTiles) {
  applyProviderSelection({
    state,
    providerSelect,
    providers: state.providers,
    renderDatasetChoices,
    updateCoverageOverlay,
    clearTiles: clearTiles ? () => { tileList.innerHTML = ""; } : null,
  });
}

function autoSelectProvider() {
  if (!state.providerAutoDetect || !state.providers.length) {
    providerModeStatus.textContent = "Manual provider selection.";
    return;
  }
  const detected = autoProviderForGeometry(
    currentGeometry(),
    state,
    state.coverageFeatures,
    state.providers.map((provider) => provider.name),
  );
  if (!detected) return;
  providerModeStatus.textContent = detected === "auto"
    ? "Auto-detect: selection crosses or is outside one provider area."
    : `Auto-detected from selection: ${providerLabel(detected)}.`;
  if (detected === state.provider) return;
  providerSelect.value = detected;
  syncProviderSelection(true);
}

function providerLabel(providerName) {
  return state.providers.find((provider) => provider.name === providerName)?.label || providerName;
}

function chooseCandidate(candidate) {
  const applied = applySearchCandidateToState({ candidate, state, variant, redrawGeometry, refreshReadout });
  if (applied.applied) {
    focusAppliedSearchResult(applied);
    searchStatus.textContent = applied.status;
    searchResults.innerHTML = "";
    return;
  }
  placeSample({ lat: candidate.lat, lon: candidate.lon }, true);
  searchStatus.textContent = `Placed ${candidate.source} result.`;
  searchResults.innerHTML = "";
}

function openSiteLinkActions(event) {
  L.DomEvent.stop(event);
  openSelectedLinkPopup({
    L,
    map,
    linkProfile,
    selectedLink: state.selectedNetworkLink,
    siteA: state.siteA,
    siteB: state.siteB,
    onCorridor: () => requestLeafletSubset(subsetRequestContext(), false),
  }, event);
}

function focusAppliedSearchResult(applied) {
  if (applied.bounds) {
    map.fitBounds(applied.bounds.map((site) => [site.lat, site.lon]), { padding: [32, 32], animate: false });
  } else if (applied.panTo) {
    map.setView([applied.panTo.lat, applied.panTo.lon], 14, { animate: false });
  }
}

function subsetRequestContext() {
  return {
    apiBaseUrl,
    confirm: (message) => window.confirm(message),
    currentGeometry,
    document,
    downloadProgress,
    downloadStatus,
    fetch,
    jobNameInput,
    map,
    openDownloadFolderButton,
    openFolderAfterDownload,
    providerCoverage,
    selectedExportProfile,
    state,
  };
}

function selectedExportProfile() {
  return document.getElementById("prototypeDownloadExportProfile")?.value || "ellipse_grd";
}

function setManualGeometry(layer) {
  state.searchSelectionActive = false;
  if (state.manualLayer) map.removeLayer(state.manualLayer);
  state.manualLayer = layer;
  state.manualGeometry = geometryFromLayer(layer, L);
  if (!state.manualGeometry) {
    map.removeLayer(layer);
    state.manualLayer = null;
    downloadStatus.textContent = "Unsupported drawing.";
    return;
  }
  watchMeasurement(layer);
  downloadStatus.textContent = `Manual ${state.manualGeometry.kind} selection ready.`;
  refreshReadout();
}

function watchMeasurement(layer) {
  if (!layer) return;
  updateMeasurement(layer);
  layer.on("pm:change", () => updateMeasurement(layer));
  layer.on("pm:edit", () => updateMeasurement(layer));
}

function updateMeasurement(layer) {
  measurementReadout.textContent = safeMeasurementText(layer, formatMeasurement);
}

function formatMeasurement(layer) {
  if (layer instanceof L.Circle) {
    const radius = layer.getRadius();
    return `Radius ${formatMeters(radius)} - Area ${formatArea(Math.PI * radius ** 2)}`;
  }
  if (layer instanceof L.Rectangle) {
    const bounds = layer.getBounds();
    if (!bounds.isValid()) return "Drawing selection...";
    const width = map.distance(bounds.getNorthWest(), bounds.getNorthEast());
    const height = map.distance(bounds.getNorthWest(), bounds.getSouthWest());
    return `${formatMeters(width)} x ${formatMeters(height)} - Area ${formatArea(width * height)}`;
  }
  if (layer instanceof L.Polygon) return `Area ${formatArea(polygonAreaM2(flattenLatLngs(layer.getLatLngs())))}`;
  return "Drawing selection...";
}

async function openLastDownloadedFolder() {
  if (!state.lastDownloadedOutputDir) {
    downloadStatus.textContent = "No downloaded output folder to open yet.";
    return;
  }

  try {
    await openDownloadedOutputFolder(state.lastDownloadedOutputDir);
    const folderName = state.lastDownloadedOutputDir.replaceAll("\\", "/").split("/").pop() || "download";
    downloadStatus.textContent = `Opened output folder for ${folderName}.`;
  } catch (_error) {
    downloadStatus.textContent = "Could not open the output folder.";
  }
}

async function openDownloadedOutputFolder(outputDir) {
  const response = await fetch(`${apiBaseUrl}/api/v1/subsets/open-folder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: outputDir })
  });
  if (!response.ok) {
    throw new Error("open-folder request failed");
  }
  return response.json();
}

function switchVariant(next) {
  const changed = changePlanningMode({
    next, search: window.location.search,
    setVariant: (value) => { variant = value; },
    heading: planningModeHeading, select: document.getElementById("variantSelect"),
    measurement: measurementReadout, configure: configureVariant,
    updateDrawingControls: (value) => updateAreaDrawingControls(map, value),
    history: window.history,
  });
  if (changed) updateSiteToggleButtons();
}

function releaseCurrentSelection() {
  clearLeafletSelection({
    state, map, redrawGeometry, refreshReadout, downloadStatus, tileList,
    releaseProvider: resetProviderDetection,
  });
}

function resetProviderDetection() {
  state.providerAutoDetect = true;
  state.provider = "auto";
  providerSelect.value = "auto";
  providerModeStatus.textContent = "Auto-detect follows the current selection.";
  if (state.providers.length) syncProviderSelection(true);
}
