// PROTOTYPE: compares a 2D Leaflet subset-selection workflow with the Cesium shell.
// Variants: corridor, area, and point. Select with ?variant=corridor|area|point.
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@geoman-io/leaflet-geoman-free";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import "./leaflet-prototype.css";
import { retryUntilReady } from "./bootstrap-retry.js";
import { clearLeafletSelection } from "./leaflet-selection.js";
import { requestLeafletSubset } from "./leaflet-subset-request.js";
import { bindPersistedInput } from "./persisted-input.js";
import { renderPrototypeShell } from "./leaflet-prototype-shell.js";
import { loadProviderCoverageCache, saveProviderCoverageCache } from "./provider-coverage-cache.js";
import { applyProviderSelection, coverageShouldShow, sortProviders } from "./provider-selection.js";
import {
  currentGeometryFrom,
  flattenLatLngs,
  formatArea,
  formatMeters,
  geometryFromLayer,
  polygonAreaM2,
  renderDatasetChoices,
} from "./leaflet-prototype-utils.js";
import {
  streets,
  satellite,
  nrwDop,
  byDop,
  thDop,
  bbDop,
  hhDop,
  shDop,
  stDop,
  nrwTopo,
  byTopo,
  nrwHillshade,
} from "./leaflet-basemaps.js";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").trim();
const bkgStateBoundaryUrl = "https://sgx.geodatenzentrum.de/wfs_vg250?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=vg250:vg250_lan&outputFormat=application%2Fjson&SRSNAME=EPSG%3A4326&COUNT=20";
const providerCoverage = {
  "lgln-ni": { stateCode: "NI", color: "#3b82f6", label: "Saxony Lower LGLN" },
  "geobasis-nrw": { stateCode: "NW", color: "#f97316", label: "NRW Geobasis" },
  "geosn-sn": { stateCode: "SN", color: "#16a34a", label: "Saxony GeoSN" },
  "hvbg-he": { stateCode: "HE", color: "#dc2626", label: "Hessen HVBG" },
  "lvermgeo-st": { stateCode: "ST", color: "#7c3aed", label: "Saxony-Anhalt LVermGeo" },
  "geobasis-bb": { stateCode: "BB", color: "#eab308", label: "Brandenburg Geobasis" },
  "lgl-bw": { stateCode: "BW", color: "#0f766e", label: "Baden-Wuerttemberg LGL" },
  "ldbv-by": { stateCode: "BY", color: "#2563eb", label: "Bayern LDBV" },
  "lgv-hh": { stateCode: "HH", color: "#0891b2", label: "Hamburg LGV" },
  "lvermgeo-sh": { stateCode: "SH", color: "#14b8a6", label: "Schleswig-Holstein LVermGeo" },
  "laiv-mv": { stateCode: "MV", color: "#a21caf", label: "Mecklenburg-Vorpommern LAiV" },
  "lginf-hb": { stateCode: "HB", color: "#65a30d", label: "Bremen Landesamt Geoinformation" },
  "gdi-be": { stateCode: "BE", color: "#4338ca", label: "Berlin GDI" },
  "tlbg-th": { stateCode: "TH", color: "#b45309", label: "Thüringen TLBG" },
};
const variants = ["corridor", "area", "point"];
const params = new URLSearchParams(window.location.search);
const variant = variants.includes(params.get("variant")) ? params.get("variant") : "corridor";
const app = document.getElementById("app");

app.innerHTML = renderPrototypeShell(variant);

const map = L.map("leafletMap", { zoomControl: true }).setView([51.1657, 10.4515], 6);
map.getContainer().classList.add("is-site-placement");
streets.addTo(map);
L.control.layers(
  {
    Streets: streets,
    Satellite: satellite,
    "NRW Ortho (DOP)": nrwDop,
    "Bayern Ortho (DOP20)": byDop,
    "Thüringen Ortho (DOP)": thDop,
    "Brandenburg Ortho (DOP20c)": bbDop,
    "Hamburg Ortho (DOP)": hhDop,
    "Schleswig-Holstein Ortho (DOP20)": shDop,
    "Sachsen-Anhalt Ortho (DOP20)": stDop,
    "NRW Topo (DTK)": nrwTopo,
    "Bayern Topo (DTK25)": byTopo
  },
  { "NRW Hillshade": nrwHillshade },
  { position: "topright" }
).addTo(map);
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
map.pm.addControls({
  position: "topleft",
  drawMarker: false,
  drawCircleMarker: false,
  drawText: false,
  drawPolyline: false,
  drawRectangle: true,
  drawPolygon: true,
  drawCircle: true,
  editMode: true,
  removalMode: true
});

const state = {
  activeSite: null,
  provider: "auto",
  providers: [],
  providerSortDirection: "asc",
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
  lastDownloadedOutputDir: null
};

const bootstrapAbortController = new AbortController();
const providerSelectionMonitor = window.setInterval(monitorProviderSelection, 250);

const placementActions = document.getElementById("placementActions");
const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const searchStatus = document.getElementById("searchStatus");
const searchResults = document.getElementById("searchResults");
const selectionReadout = document.getElementById("selectionReadout");
const downloadStatus = document.getElementById("downloadStatus");
const tileList = document.getElementById("tileList");
const providerSelect = document.getElementById("providerSelect");
const providerSortSelect = document.getElementById("providerSortSelect");
const jobNameInput = document.getElementById("jobNameInput");
const measurementReadout = document.getElementById("measurementReadout");
const coverageToggle = document.getElementById("coverageToggle");
const openFolderAfterDownload = document.getElementById("openFolderAfterDownload");
const openDownloadFolderButton = document.getElementById("btnOpenDownloadFolder");
bindPersistedInput(searchInput, "multiplanner.leaflet.searchInput");

configureVariant();
refreshReadout();
bootstrapApi();
loadProviderCoverage();

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
  if (!state.isDrawing) placeFromMap(event.latlng);
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
searchButton.addEventListener("click", searchPlaces);
searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    searchPlaces();
  }
});
document.getElementById("locateButton").addEventListener("click", () => requestLeafletSubset(subsetRequestContext(), false));
document.getElementById("downloadButton").addEventListener("click", () => requestLeafletSubset(subsetRequestContext(), true));
document.getElementById("clearButton").addEventListener("click", () => clearLeafletSelection({ state, map, redrawGeometry, refreshReadout, downloadStatus, tileList }));
openDownloadFolderButton.addEventListener("click", openLastDownloadedFolder);
document.getElementById("previousVariant").addEventListener("click", () => switchVariant(-1));
document.getElementById("nextVariant").addEventListener("click", () => switchVariant(1));
providerSelect.addEventListener("input", handleProviderSelection);
providerSelect.addEventListener("change", handleProviderSelection);
providerSortSelect.addEventListener("input", handleProviderSortChange);
coverageToggle.addEventListener("change", updateCoverageOverlay);

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
  if (variant === "corridor") {
    if (state.siteA) state.markers.push(circle(state.siteA, "#00c7ff", "A"));
    if (state.siteB) state.markers.push(circle(state.siteB, "#ff9f43", "B"));
    if (state.siteA && state.siteB) state.line = L.polyline([[state.siteA.lat, state.siteA.lon], [state.siteB.lat, state.siteB.lon]], { color: "#7dff8c", weight: 4 }).addTo(map);
  }
  if (variant === "point" && state.point) state.markers.push(circle(state.point, "#ffdd57", "P"));
}

function circle(sample, color, label) {
  return L.circleMarker([sample.lat, sample.lon], { radius: 8, color, fillColor: color, fillOpacity: 0.9, weight: 2 }).bindTooltip(label, { permanent: true, direction: "top" }).addTo(map);
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
  if (state.manualGeometry) {
    selectionReadout.textContent = `Manual ${state.manualGeometry.kind} selection\nDraw tools override the site/corridor selection.`;
    return;
  }
  if (variant === "corridor") {
    selectionReadout.textContent = `Active: ${state.activeSite ? `Site ${state.activeSite}` : "none"}\nA: ${sampleText(state.siteA)}\nB: ${sampleText(state.siteB)}`;
    updateSiteToggleButtons();
  } else if (variant === "area") {
    selectionReadout.textContent = state.rectangle ? `${state.rectangle.getBounds().toBBoxString()}\nW, S, E, N` : "Click two rectangle corners.";
  } else {
    selectionReadout.textContent = sampleText(state.point);
  }
}

function toggleActiveSite(site) {
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
  return sample ? `${sample.lat.toFixed(6)}, ${sample.lon.toFixed(6)}` : "not set";
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
  syncProviderSelection(true);
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

async function searchPlaces() {
  const query = searchInput.value.trim();
  if (!query) return;
  searchStatus.textContent = "Searching...";
  searchResults.innerHTML = "";
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/search/places?q=${encodeURIComponent(query)}`);
    if (!response.ok) throw new Error("Search failed");
    const payload = await response.json();
    const candidates = payload.candidates || [];
    if (candidates.length === 1 && candidates[0].source === "coordinates") {
      chooseCandidate(candidates[0]);
      return;
    }
    for (const candidate of candidates) {
      const button = document.createElement("button");
      button.className = "prototype-result";
      button.textContent = candidate.label;
      button.addEventListener("click", () => chooseCandidate(candidate));
      searchResults.appendChild(button);
    }
    searchStatus.textContent = candidates.length ? "Choose a result." : "No matches found.";
  } catch {
    searchStatus.textContent = "Search failed.";
  }
}

function chooseCandidate(candidate) {
  placeSample({ lat: candidate.lat, lon: candidate.lon }, true);
  searchStatus.textContent = `Placed ${candidate.source} result.`;
  searchResults.innerHTML = "";
}

function subsetRequestContext() {
  return {
    apiBaseUrl,
    confirm: (message) => window.confirm(message),
    currentGeometry,
    document,
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
  return document.querySelector('input[name="prototypeDownloadExportProfile"]:checked')?.value || "ellipse_grd";
}

function setManualGeometry(layer) {
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
  updateMeasurement(layer);
  layer.on("pm:change", () => updateMeasurement(layer));
  layer.on("pm:edit", () => updateMeasurement(layer));
}

function updateMeasurement(layer) {
  measurementReadout.textContent = formatMeasurement(layer);
}

function formatMeasurement(layer) {
  if (layer instanceof L.Circle) {
    const radius = layer.getRadius();
    return `Radius ${formatMeters(radius)} - Area ${formatArea(Math.PI * radius ** 2)}`;
  }
  if (layer instanceof L.Rectangle) {
    const bounds = layer.getBounds();
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

async function loadProviderCoverage() {
  const cachedFeatures = loadProviderCoverageCache();
  if (cachedFeatures) {
    applyProviderCoverage(cachedFeatures);
  }
  try {
    const response = await fetch(bkgStateBoundaryUrl);
    if (!response.ok) throw new Error("Boundary service unavailable");
    const collection = await response.json();
    const featuresByProvider = {};
    for (const [provider, config] of Object.entries(providerCoverage)) {
      const feature = collection.features.find((candidate) => candidate.properties.lkz === config.stateCode);
      if (feature) {
        featuresByProvider[provider] = feature;
      }
    }
    map.attributionControl.addAttribution("BKG, VG250, dl-de/by-2-0");
    saveProviderCoverageCache(featuresByProvider);
    applyProviderCoverage(featuresByProvider);
  } catch {
    if (!cachedFeatures) {
      downloadStatus.textContent = "Provider coverage outline could not be loaded.";
    }
  }
}

function applyProviderCoverage(featuresByProvider) {
  for (const layer of Object.values(state.coverageLayers)) {
    if (map.hasLayer(layer)) {
      map.removeLayer(layer);
    }
  }
  state.coverageLayers = {};
  state.coverageFeatures = {};

  for (const [provider, feature] of Object.entries(featuresByProvider)) {
    const config = providerCoverage[provider];
    if (!config) continue;
    state.coverageLayers[provider] = L.geoJSON(feature, { style: { color: config.color, weight: 2, fillColor: config.color, fillOpacity: 0.12 } });
    state.coverageFeatures[provider] = feature;
  }
  updateCoverageOverlay();
}

function updateCoverageOverlay() {
  for (const [provider, layer] of Object.entries(state.coverageLayers)) {
    const shouldShow = coverageShouldShow(state.provider, provider, coverageToggle.checked);
    if (shouldShow && !map.hasLayer(layer)) layer.addTo(map);
    if (!shouldShow && map.hasLayer(layer)) map.removeLayer(layer);
  }
}

function switchVariant(step) {
  const currentIndex = variants.indexOf(variant);
  const next = variants[(currentIndex + step + variants.length) % variants.length];
  params.set("variant", next);
  window.location.search = params.toString();
}
