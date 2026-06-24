// PROTOTYPE: compares a 2D Leaflet subset-selection workflow with the Cesium shell.
// Variants: corridor, area, and point. Select with ?variant=corridor|area|point.
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@geoman-io/leaflet-geoman-free";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import "./leaflet-prototype.css";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").trim();
const bkgStateBoundaryUrl = "https://sgx.geodatenzentrum.de/wfs_vg250?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=vg250:vg250_lan&outputFormat=application%2Fjson&SRSNAME=EPSG%3A4326&COUNT=20";
const providerCoverage = {
  "lgln-ni": { stateCode: "NI", color: "#3b82f6", label: "LGLN Lower Saxony" },
  "geobasis-nrw": { stateCode: "NW", color: "#f97316", label: "Geobasis NRW" }
};
const variants = ["corridor", "area", "point"];
const labels = {
  corridor: "A — Two sites / corridor",
  area: "B — Draw rectangular area",
  point: "C — Single point"
};
const params = new URLSearchParams(window.location.search);
const variant = variants.includes(params.get("variant")) ? params.get("variant") : "corridor";
const app = document.getElementById("app");

app.innerHTML = `
  <main class="leaflet-prototype-shell">
    <aside class="leaflet-prototype-panel">
      <div class="prototype-kicker">PROTOTYPE · 2D local planning</div>
      <h1>${labels[variant]}</h1>
      <p id="modeHelp" class="prototype-help"></p>
      <div class="prototype-actions" id="placementActions"></div>
      <label for="searchInput">Search place or coordinates</label>
      <div class="prototype-search-row">
        <input id="searchInput" placeholder="52.324784, 7.467435 or address" />
        <button id="searchButton">Find</button>
      </div>
      <div id="searchStatus" class="prototype-status">API: starting</div>
      <div id="searchResults" class="prototype-results"></div>
      <label for="providerSelect">Data provider</label>
      <select id="providerSelect"><option value="geobasis-nrw">Geobasis NRW</option></select>
      <label class="prototype-coverage-toggle"><input id="coverageToggle" type="checkbox" checked /> Show selected provider coverage</label>
      <fieldset id="datasetChoices" class="prototype-datasets"></fieldset>
      <section class="prototype-selection">
        <h2>Current selection</h2>
        <pre id="selectionReadout">none</pre>
      </section>
      <div class="prototype-actions prototype-download-actions">
        <button id="locateButton" class="secondary">Preview 1 m subset</button>
        <button id="downloadButton">Download + Ellipse export</button>
        <button id="clearButton" class="secondary">Clear selection</button>
      </div>
      <div id="downloadStatus" class="prototype-status">Choose a geometry on the map.</div>
      <div id="tileList" class="prototype-tile-list"></div>
      <p class="prototype-note">Downloads use the existing provider API and Ellipse GeoTIFF + TAB export path.</p>
    </aside>
    <section class="leaflet-prototype-map-wrap">
      <div id="leafletMap"></div>
      <div class="prototype-map-note">Use the layer button for street or satellite imagery. Draw tools select download areas.</div>
      <div id="measurementReadout" class="prototype-measurement">Draw a circle, rectangle, or lasso to see dimensions.</div>
    </section>
    <nav class="prototype-switcher" aria-label="Prototype variants">
      <button id="previousVariant" aria-label="Previous variant">←</button>
      <strong id="variantLabel">${labels[variant]}</strong>
      <button id="nextVariant" aria-label="Next variant">→</button>
      <a href="?renderer=cesium">Open Cesium comparison</a>
    </nav>
  </main>
`;

const map = L.map("leafletMap", { zoomControl: true }).setView([51.1657, 10.4515], 6);
map.getContainer().classList.add("is-site-placement");
const streets = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "© OpenStreetMap contributors"
});
const satellite = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  { maxZoom: 19, attribution: "Tiles © Esri" }
);
streets.addTo(map);
L.control.layers({ Streets: streets, Satellite: satellite }, undefined, { position: "topright" }).addTo(map);
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
  provider: "geobasis-nrw",
  providers: [],
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
  coverageLayers: {}
};

const placementActions = document.getElementById("placementActions");
const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const searchStatus = document.getElementById("searchStatus");
const searchResults = document.getElementById("searchResults");
const selectionReadout = document.getElementById("selectionReadout");
const downloadStatus = document.getElementById("downloadStatus");
const tileList = document.getElementById("tileList");
const providerSelect = document.getElementById("providerSelect");
const measurementReadout = document.getElementById("measurementReadout");
const coverageToggle = document.getElementById("coverageToggle");

configureVariant();
refreshReadout();
bootstrapApi();
loadProviderCoverage();

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
document.getElementById("locateButton").addEventListener("click", () => requestSubset(false));
document.getElementById("downloadButton").addEventListener("click", () => requestSubset(true));
document.getElementById("clearButton").addEventListener("click", clearSelection);
document.getElementById("previousVariant").addEventListener("click", () => switchVariant(-1));
document.getElementById("nextVariant").addEventListener("click", () => switchVariant(1));
providerSelect.addEventListener("change", () => {
  state.provider = providerSelect.value;
  const provider = state.providers.find((entry) => entry.name === state.provider);
  renderDatasetChoices(provider?.datasets || []);
  updateCoverageOverlay();
  tileList.innerHTML = "";
});
coverageToggle.addEventListener("change", updateCoverageOverlay);

function configureVariant() {
  const help = document.getElementById("modeHelp");
  if (variant === "corridor") {
    help.textContent = "Place one site to fetch its tile coverage, or place Site A and Site B to fetch a buffered corridor between them.";
    placementActions.innerHTML = '<button id="siteAButton" class="secondary">Place Site A</button><button id="siteBButton" class="secondary">Place Site B</button><div id="sitePlacementStatus" class="placement-state"></div>';
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
  if (state.manualGeometry) return state.manualGeometry;
  if (variant === "corridor") {
    if (state.siteA && state.siteB) {
      return { kind: "corridor", from_lon: state.siteA.lon, from_lat: state.siteA.lat, to_lon: state.siteB.lon, to_lat: state.siteB.lat, buffer_m: 75 };
    }
    const site = state.siteA || state.siteB;
    return site ? { kind: "point", lon: site.lon, lat: site.lat } : null;
  }
  if (variant === "area") {
    if (!state.rectangle) return null;
    const bounds = state.rectangle.getBounds();
    return { kind: "bbox", west: bounds.getWest(), south: bounds.getSouth(), east: bounds.getEast(), north: bounds.getNorth() };
  }
  if (!state.point) return null;
  return { kind: "point", lon: state.point.lon, lat: state.point.lat };
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
  if (placementStatus) placementStatus.textContent = state.activeSite ? `Site ${state.activeSite} armed — click the map to place it.` : "No site armed — select Site A or Site B.";
  for (const site of ["A", "B"]) {
    document.getElementById(`site${site}Button`)?.classList.toggle("is-active", state.activeSite === site);
  }
}

function sampleText(sample) {
  return sample ? `${sample.lat.toFixed(6)}, ${sample.lon.toFixed(6)}` : "not set";
}

async function bootstrapApi() {
  try {
    const [healthResponse, providersResponse] = await Promise.all([
      fetch(`${apiBaseUrl}/healthz`),
      fetch(`${apiBaseUrl}/api/v1/providers`)
    ]);
    if (!healthResponse.ok || !providersResponse.ok) throw new Error("API unavailable");
    const payload = await providersResponse.json();
    state.providers = payload.providers || [];
    providerSelect.innerHTML = "";
    for (const provider of state.providers) {
      const option = document.createElement("option");
      option.value = provider.name;
      option.textContent = provider.label;
      option.selected = provider.name === state.provider;
      providerSelect.appendChild(option);
    }
    if (!state.providers.some((provider) => provider.name === state.provider)) {
      state.provider = state.providers[0]?.name || "";
      providerSelect.value = state.provider;
    }
    renderDatasetChoices(state.providers.find((provider) => provider.name === state.provider)?.datasets || []);
    searchStatus.textContent = "API ready";
  } catch {
    searchStatus.textContent = "API unavailable";
  }
}

async function searchPlaces() {
  const query = searchInput.value.trim();
  if (!query) return;
  searchStatus.textContent = "Searching…";
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

async function requestSubset(download) {
  const geometry = currentGeometry();
  if (!geometry) {
    downloadStatus.textContent = "Complete the selection first.";
    return;
  }
  downloadStatus.textContent = download ? "Downloading 1 m data and creating Ellipse export…" : "Resolving available 1 m tiles…";
  const endpoint = download ? "/api/v1/subsets/download" : "/api/v1/subsets/locate";
  const datasets = selectedDatasets();
  if (!datasets.length) {
    downloadStatus.textContent = "Choose at least one dataset.";
    return;
  }
  const body = { provider: state.provider, datasets, geometry };
  if (download) {
    body.selection_name = `leaflet_${geometry.kind}`;
    body.export_profile = "ellipse_mapinfo_tab";
  }
  try {
    const response = await fetch(`${apiBaseUrl}${endpoint}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!response.ok) throw new Error("Subset request failed");
    const payload = await response.json();
    if (download) {
      downloadStatus.textContent = `Saved ${payload.file_count} source files. Ellipse exports: ${payload.exports.length}.\n${payload.output_dir}`;
      renderTiles(payload.files.map((file) => ({ dataset: file.dataset, tileId: file.tile_id, path: file.saved_path })));
    } else {
      downloadStatus.textContent = payload.results.map((result) => `${result.dataset}: ${result.match_count} tiles`).join(" · ");
      renderTiles(payload.results.flatMap((result) => result.tiles.map((tile) => ({ dataset: result.dataset, tileId: tile.tile_id, path: tile.primary_url }))));
    }
  } catch {
    downloadStatus.textContent = download ? "Download/export failed." : "Subset lookup failed.";
  }
}

function clearSelection() {
  state.siteA = null;
  state.siteB = null;
  state.point = null;
  state.areaStart = null;
  if (state.rectangle) map.removeLayer(state.rectangle);
  state.rectangle = null;
  if (state.manualLayer) map.removeLayer(state.manualLayer);
  state.manualLayer = null;
  state.manualGeometry = null;
  redrawGeometry();
  refreshReadout();
  downloadStatus.textContent = "Selection cleared.";
  tileList.innerHTML = "";
}

function setManualGeometry(layer) {
  if (state.manualLayer) map.removeLayer(state.manualLayer);
  state.manualLayer = layer;
  state.manualGeometry = geometryFromLayer(layer);
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
    return `Radius ${formatMeters(radius)} · Area ${formatArea(Math.PI * radius ** 2)}`;
  }
  if (layer instanceof L.Rectangle) {
    const bounds = layer.getBounds();
    const width = map.distance(bounds.getNorthWest(), bounds.getNorthEast());
    const height = map.distance(bounds.getNorthWest(), bounds.getSouthWest());
    return `${formatMeters(width)} × ${formatMeters(height)} · Area ${formatArea(width * height)}`;
  }
  if (layer instanceof L.Polygon) {
    const points = flattenLatLngs(layer.getLatLngs());
    return `Area ${formatArea(polygonAreaM2(points))}`;
  }
  return "Drawing selection…";
}

function polygonAreaM2(points) {
  const radius = 6371000;
  return Math.abs(points.reduce((sum, point, index) => {
    const next = points[(index + 1) % points.length];
    return sum + (next.lng - point.lng) * Math.PI / 180 * (2 + Math.sin(point.lat * Math.PI / 180) + Math.sin(next.lat * Math.PI / 180));
  }, 0) * radius ** 2 / 2);
}

function formatMeters(value) {
  return value >= 1000 ? `${(value / 1000).toFixed(2)} km` : `${Math.round(value)} m`;
}

function formatArea(value) {
  return value >= 1_000_000 ? `${(value / 1_000_000).toFixed(2)} km²` : `${Math.round(value).toLocaleString()} m²`;
}

async function loadProviderCoverage() {
  try {
    const response = await fetch(bkgStateBoundaryUrl);
    if (!response.ok) throw new Error("Boundary service unavailable");
    const collection = await response.json();
    for (const [provider, config] of Object.entries(providerCoverage)) {
      const feature = collection.features.find((candidate) => candidate.properties.lkz === config.stateCode);
      if (feature) state.coverageLayers[provider] = L.geoJSON(feature, { style: { color: config.color, weight: 2, fillColor: config.color, fillOpacity: 0.12 } });
    }
    map.attributionControl.addAttribution("© BKG, VG250, dl-de/by-2-0");
    updateCoverageOverlay();
  } catch {
    downloadStatus.textContent = "Provider coverage outline could not be loaded.";
  }
}

function updateCoverageOverlay() {
  for (const [provider, layer] of Object.entries(state.coverageLayers)) {
    const shouldShow = coverageToggle.checked && provider === state.provider;
    if (shouldShow && !map.hasLayer(layer)) layer.addTo(map);
    if (!shouldShow && map.hasLayer(layer)) map.removeLayer(layer);
  }
}

function geometryFromLayer(layer) {
  if (layer instanceof L.Rectangle) {
    const bounds = layer.getBounds();
    return { kind: "bbox", west: bounds.getWest(), south: bounds.getSouth(), east: bounds.getEast(), north: bounds.getNorth() };
  }
  if (layer instanceof L.Circle) {
    return { kind: "polygon", coordinates: circleCoordinates(layer.getLatLng(), layer.getRadius()) };
  }
  if (layer instanceof L.Polygon) {
    return { kind: "polygon", coordinates: flattenLatLngs(layer.getLatLngs()).map((latlng) => [latlng.lng, latlng.lat]) };
  }
  return null;
}

function flattenLatLngs(values) {
  return values.flatMap((value) => Array.isArray(value) ? flattenLatLngs(value) : [value]);
}

function circleCoordinates(center, radiusM) {
  const earthRadiusM = 6371000;
  const latRadians = center.lat * Math.PI / 180;
  return Array.from({ length: 32 }, (_, index) => {
    const angle = index * 2 * Math.PI / 32;
    const lat = center.lat + (radiusM * Math.cos(angle) / earthRadiusM) * 180 / Math.PI;
    const lon = center.lng + (radiusM * Math.sin(angle) / (earthRadiusM * Math.cos(latRadians))) * 180 / Math.PI;
    return [lon, lat];
  });
}

function selectedDatasets() {
  return [...document.querySelectorAll('input[name="dataset"]:checked')].map((input) => input.value);
}

function renderDatasetChoices(datasets) {
  const labels = {
    dgm1: "DGM1 · 1 m terrain",
    dom1: "DOM1 · 1 m surface",
    dop20: "DOP20 · 20 cm orthophoto"
  };
  const fieldset = document.getElementById("datasetChoices");
  fieldset.innerHTML = "<legend>Download datasets</legend>";
  for (const dataset of datasets) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "dataset";
    input.value = dataset;
    input.checked = true;
    label.append(input, ` ${labels[dataset] || dataset}`);
    fieldset.appendChild(label);
  }
}

function renderTiles(tiles) {
  if (!tiles.length) {
    tileList.textContent = "No provider tiles matched this selection.";
    return;
  }
  tileList.innerHTML = `<strong>Tiles (${tiles.length})</strong><ul>${tiles.map((tile) => `<li><code>${escapeHtml(tile.dataset)}/${escapeHtml(tile.tileId || "unnamed-tile")}</code><br /><small>${escapeHtml(tile.path || "")}</small></li>`).join("")}</ul>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function switchVariant(step) {
  const currentIndex = variants.indexOf(variant);
  const next = variants[(currentIndex + step + variants.length) % variants.length];
  params.set("variant", next);
  window.location.search = params.toString();
}
