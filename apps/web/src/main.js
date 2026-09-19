import "cesium/Build/Cesium/Widgets/widgets.css";
import "./style.css";
import * as Cesium from "cesium";
import { retryUntilReady } from "./bootstrap-retry.js";
import { createGeometryTools } from "./cesium-geometry-tools.js";
import { distanceMeters } from "./cesium-geometry.js";
import { renderCesiumShell } from "./cesium-shell.js";
import { createCorridorFlow } from "./corridor-flow.js";
import { requestLeafletSubset } from "./leaflet-subset-request.js";
import { renderDatasetChoices } from "./leaflet-prototype-utils.js";
import { createLinkProfileWindow } from "./link-profile-window.js";
import { providerDatasets } from "./provider-selection.js";

window.CESIUM_BASE_URL = "/node_modules/cesium/Build/Cesium";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? window.location.origin).trim();
const cesiumIonToken = (import.meta.env.VITE_CESIUM_ION_TOKEN || "").trim();
const useWorldTerrain = (import.meta.env.VITE_USE_WORLD_TERRAIN || "false").trim().toLowerCase() === "true";

if (cesiumIonToken) {
  Cesium.Ion.defaultAccessToken = cesiumIonToken;
}

const app = document.getElementById("app");
app.innerHTML = renderCesiumShell(useWorldTerrain);

const viewer = new Cesium.Viewer("cesiumContainer", {
  animation: false,
  timeline: false,
  sceneModePicker: false,
  baseLayerPicker: true,
  scene3DOnly: true,
  orderIndependentTranslucency: false,
  requestRenderMode: true,
  maximumRenderTimeChange: Infinity,
  msaaSamples: 1,
  ...(useWorldTerrain
    ? { terrain: Cesium.Terrain.fromWorldTerrain() }
    : { terrainProvider: new Cesium.EllipsoidTerrainProvider() })
});
const linkProfileWindow = createLinkProfileWindow({
  parent: document.querySelector(".map-stage"),
  apiBaseUrl,
  fetchWithTimeout,
});

viewer.scene.globe.enableLighting = false;
viewer.scene.skyAtmosphere.show = false;
viewer.scene.globe.showGroundAtmosphere = false;
viewer.scene.fog.enabled = false;
viewer.scene.globe.preloadAncestors = false;
viewer.scene.globe.tileCacheSize = 25;
viewer.resolutionScale = 1;
viewer.scene.globe.maximumScreenSpaceError = 6;
viewer.scene.globe.loadingDescendantLimit = 5;
viewer.scene.screenSpaceCameraController.inertiaSpin = 0.75;
viewer.scene.screenSpaceCameraController.inertiaTranslate = 0.75;
viewer.scene.screenSpaceCameraController.inertiaZoom = 0.6;
viewer.camera.setView({
  destination: Cesium.Cartesian3.fromDegrees(10.45, 51.16, 650000)
});

const btnSiteA = document.getElementById("btnSiteA");
const btnSiteB = document.getElementById("btnSiteB");
const btnCenter = document.getElementById("btnCenter");
const btnClear = document.getElementById("btnClear");
const btnSearch = document.getElementById("btnSearch");
const apiStatus = document.getElementById("apiStatus");
const providerMode = document.getElementById("providerMode");
const selectionModeEl = document.getElementById("selectionMode");
const terrainModeEl = document.getElementById("terrainMode");
const searchInput = document.getElementById("searchInput");
const searchStatus = document.getElementById("searchStatus");
const searchResults = document.getElementById("searchResults");
const siteAValue = document.getElementById("siteAValue");
const siteBValue = document.getElementById("siteBValue");

const btnLocate = document.getElementById("btnLocate");
const btnDownload = document.getElementById("btnDownload");
const btnOpenDownloadFolder = document.getElementById("btnOpenDownloadFolder");
const lookupStatus = document.getElementById("lookupStatus");
const openFolderAfterDownload = document.getElementById("openFolderAfterDownload");
const providerSelect = document.getElementById("providerSelect");
const jobNameInput = document.getElementById("jobNameInput");
const downloadProgress = document.getElementById("downloadProgress");
const geometryStatus = document.getElementById("geometryStatus");

const state = {
  selectionMode: "A",
  siteA: null,
  siteB: null,
  siteAEntity: null,
  siteBEntity: null,
  linkEntity: null,
  linkProfileDatasets: ["dgm1", "dom1"],
  apiReady: false,
  lastSelectedSearchLabel: null,
  lastDownloadedOutputDir: null,
  provider: "auto",
  providers: [],
  coverageFeatures: {},
  downloadTiles: [],
  geometryMode: "corridor",
  geometryDraft: null,
  manualGeometry: null,
  manualEntity: null,
  previewEntity: null,
  point: null,
};

const bootstrapAbortController = new AbortController();
const corridorFlow = createCorridorFlow({
  apiBaseUrl,
  state,
  lookupStatus,
  btnOpenDownloadFolder,
  openFolderAfterDownload,
  fetchWithTimeout,
});
const geometryTools = createGeometryTools({
  Cesium,
  viewer,
  state,
  beforeSample: pickedLinkEntity,
  onCorridorSample: assignSampleToActiveSite,
  onGeometryChange: updateReadout,
  setStatus: (message) => { geometryStatus.textContent = message; },
});
const subsetContext = {
  apiBaseUrl,
  confirm: (message) => window.confirm(message),
  currentGeometry: geometryTools.currentGeometry,
  document,
  downloadProgress,
  downloadStatus: lookupStatus,
  fetch,
  jobNameInput,
  map: { distance: ([latA, lonA], [latB, lonB]) => distanceMeters({ lat: latA, lon: lonA }, { lat: latB, lon: lonB }) },
  openDownloadFolderButton: btnOpenDownloadFolder,
  openFolderAfterDownload,
  providerCoverage: {},
  selectedExportProfile,
  state,
};

btnSiteA.addEventListener("click", () => setSelectionMode("A"));
btnSiteB.addEventListener("click", () => setSelectionMode("B"));
btnCenter.addEventListener("click", centerActiveSite);
btnClear.addEventListener("click", clearSelections);
btnSearch.addEventListener("click", runSearch);
btnLocate.addEventListener("click", () => requestLeafletSubset(subsetContext, false));
btnDownload.addEventListener("click", () => requestLeafletSubset(subsetContext, true));
btnOpenDownloadFolder.addEventListener("click", corridorFlow.openLastDownloadedFolder);
providerSelect.addEventListener("change", updateProviderSelection);
for (const input of document.querySelectorAll('input[name="geometryMode"]')) {
  input.addEventListener("change", () => geometryTools.setMode(input.value));
}
openFolderAfterDownload.addEventListener("change", () => {
  btnOpenDownloadFolder.hidden = !state.lastDownloadedOutputDir;
});
searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    runSearch();
  }
});

setSelectionMode("A");
updateReadout();
bootstrapApiState();

if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    bootstrapAbortController.abort();
    geometryTools.destroy();
    linkProfileWindow.destroy();
    viewer.destroy();
  });
}

window.addEventListener(
  "beforeunload",
  () => {
    bootstrapAbortController.abort();
  },
  { once: true }
);

function setSelectionMode(mode) {
  state.selectionMode = mode;
  selectionModeEl.textContent = mode === "A" ? "Site A" : "Site B";
  searchStatus.textContent = `search will place Site ${mode}`;
}

function clearSelections() {
  if (state.siteAEntity) {
    viewer.entities.remove(state.siteAEntity);
  }
  if (state.siteBEntity) {
    viewer.entities.remove(state.siteBEntity);
  }
  if (state.linkEntity) {
    viewer.entities.remove(state.linkEntity);
  }

  state.siteA = null;
  state.siteB = null;
  state.siteAEntity = null;
  state.siteBEntity = null;
  state.linkEntity = null;
  state.lastSelectedSearchLabel = null;
  geometryTools.clear();
  linkProfileWindow.close();
  setSelectionMode("A");
  searchResults.innerHTML = "";
  updateReadout();
  viewer.scene.requestRender();
}

function assignSampleToActiveSite(sample) {
  if (state.selectionMode === "A") {
    state.siteA = sample;
    upsertSite("A", sample);
  } else {
    state.siteB = sample;
    upsertSite("B", sample);
  }

  renderLink();
  updateReadout();
  viewer.scene.requestRender();
}

function centerActiveSite() {
  const sample = state.selectionMode === "A" ? state.siteA : state.siteB;
  if (!sample) {
    searchStatus.textContent = `set Site ${state.selectionMode} first`;
    return;
  }

  viewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(sample.lon, sample.lat, 1000)
  });
  viewer.scene.requestRender();
}

function upsertSite(kind, sample) {
  const existing = kind === "A" ? state.siteAEntity : state.siteBEntity;
  if (existing) {
    updateSiteEntity(existing, kind, sample);
    return;
  }

  const entity = createSiteEntity(kind, sample);
  if (kind === "A") state.siteAEntity = entity;
  else state.siteBEntity = entity;
}

function updateSiteEntity(entity, kind, sample) {
  entity.position = Cesium.Cartesian3.fromDegrees(sample.lon, sample.lat, sample.height);
  entity.label.text = siteLabel(kind, sample);
}

function createSiteEntity(kind, sample) {
  const id = kind === "A" ? "site-a" : "site-b";
  const color = kind === "A" ? Cesium.Color.CYAN : Cesium.Color.ORANGE;
  return viewer.entities.add({
    id,
    position: Cesium.Cartesian3.fromDegrees(sample.lon, sample.lat, sample.height),
    point: {
      pixelSize: 12,
      color,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 1
    },
    label: {
      text: siteLabel(kind, sample),
      showBackground: true,
      backgroundColor: Cesium.Color.fromCssColorString("#10263b"),
      pixelOffset: new Cesium.Cartesian2(0, -24),
      font: "14px IBM Plex Sans"
    }
  });
}

function renderLink() {
  if (state.linkEntity) {
    viewer.entities.remove(state.linkEntity);
    state.linkEntity = null;
  }

  if (!(state.siteA && state.siteB)) {
    return;
  }

  state.linkEntity = viewer.entities.add({
    id: "site-a-b-link",
    name: "Site A to Site B",
    polyline: {
      positions: Cesium.Cartesian3.fromDegreesArrayHeights([
        state.siteA.lon,
        state.siteA.lat,
        state.siteA.height,
        state.siteB.lon,
        state.siteB.lat,
        state.siteB.height
      ]),
      width: 5,
      material: Cesium.Color.LIME
    }
  });
}

function pickedLinkEntity(screenPosition) {
  const picked = viewer.scene.pick(screenPosition);
  if (!(Cesium.defined(picked) && picked.id === state.linkEntity)) return false;
  openLinkProfileWindow();
  return true;
}

function openLinkProfileWindow() {
  if (!(state.siteA && state.siteB)) return;
  linkProfileWindow.open({
    siteA: state.siteA,
    siteB: state.siteB,
    availableDatasets: state.linkProfileDatasets,
  });
  searchStatus.textContent = "opened link profile settings";
}

function siteLabel(kind, sample) {
  return `${kind}: ${sample.lon.toFixed(5)}, ${sample.lat.toFixed(5)}`;
}

function updateReadout() {
  siteAValue.textContent = state.siteA ? formatSample(state.siteA) : "not set";
  siteBValue.textContent = state.siteB ? formatSample(state.siteB) : "not set";
  const geometry = geometryTools.currentGeometry();
  btnLocate.disabled = !geometry;
  btnDownload.disabled = !geometry;
  if (!geometry) {
    lookupStatus.textContent = "complete a selection";
  }
}

function selectedExportProfile() {
  return document.querySelector('input[name="downloadExportProfile"]:checked')?.value || "ellipse_grd";
}

function updateProviderSelection() {
  state.provider = providerSelect.value;
  renderDatasetChoices(providerDatasets(state.providers, state.provider));
}

function formatSample(sample) {
  return `${sample.lon.toFixed(5)}, ${sample.lat.toFixed(5)} @ ${sample.height.toFixed(1)} m`;
}

async function bootstrapApiState() {
  terrainModeEl.textContent = useWorldTerrain ? "world terrain" : "fast local";
  apiStatus.textContent = "starting";
  providerMode.textContent = "waiting for backend";
  await retryUntilReady(async () => {
    const [healthResponse, configResponse, providersResponse] = await Promise.all([
      fetchWithTimeout(`${apiBaseUrl}/healthz`, { timeoutMs: 2000 }),
      fetchWithTimeout(`${apiBaseUrl}/api/v1/config`, { timeoutMs: 2000 }),
      fetchWithTimeout(`${apiBaseUrl}/api/v1/providers`, { timeoutMs: 2000 }),
    ]);

    if (!healthResponse.ok || !configResponse.ok || !providersResponse.ok) {
      throw new Error("API bootstrap failed");
    }

    const health = await healthResponse.json();
    const config = await configResponse.json();
    const providers = await providersResponse.json();
    apiStatus.textContent = health.status;
    providerMode.textContent = config.provider_mode;
    state.providers = providers.providers || [];
    providerSelect.innerHTML = state.providers.map((provider) => (
      `<option value="${provider.name}">${provider.label}</option>`
    )).join("");
    providerSelect.value = state.providers.some((provider) => provider.name === "auto")
      ? "auto"
      : state.providers[0]?.name || "";
    updateProviderSelection();
    state.apiReady = true;
  }, {
    signal: bootstrapAbortController.signal,
    delayMs: 1000,
    onRetry: () => {
      if (!state.apiReady) {
        apiStatus.textContent = "starting";
        providerMode.textContent = "waiting for backend";
      }
    },
  });
}

async function fetchWithTimeout(url, { timeoutMs = 2000, ...options } = {}) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal
    });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

async function runSearch() {
  if (!state.apiReady) {
    searchStatus.textContent = "backend still starting";
    return;
  }

  const query = searchInput.value.trim();
  if (!query) {
    searchStatus.textContent = "enter coordinates or an address";
    return;
  }

  searchStatus.textContent = "searching";
  searchResults.innerHTML = "";
  try {
    const payload = await searchPlaces(query);
    const candidates = payload.candidates || [];
    renderSearchResults(candidates);
    if (candidates.length === 1 && candidates[0].source === "coordinates") {
      await placeSearchCandidate(candidates[0]);
      return;
    }
    searchStatus.textContent = candidates.length
      ? `select a result for Site ${state.selectionMode}`
      : "no matches found";
  } catch (_error) {
    searchStatus.textContent = "search failed";
  }
}

async function searchPlaces(query) {
  const response = await fetchWithTimeout(
    `${apiBaseUrl}/api/v1/search/places?q=${encodeURIComponent(query)}`,
    { timeoutMs: 5000 }
  );
  if (!response.ok) {
    throw new Error("search failed");
  }
  return response.json();
}

function renderSearchResults(candidates) {
  searchResults.innerHTML = "";
  for (const candidate of candidates) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "search-result";
    button.textContent = candidate.label;
    if (candidate.label === state.lastSelectedSearchLabel) {
      button.classList.add("is-selected");
    }
    button.addEventListener("click", async () => {
      button.classList.add("is-pending");
      await placeSearchCandidate(candidate, candidates);
    });
    searchResults.appendChild(button);
  }
}

async function placeSearchCandidate(candidate, candidates = [candidate]) {
  searchStatus.textContent = `placing Site ${state.selectionMode}...`;
  const sample = {
    lon: candidate.lon,
    lat: candidate.lat,
    height: await sampleTerrainHeight(candidate.lon, candidate.lat)
  };
  const targetSite = state.selectionMode;
  state.lastSelectedSearchLabel = candidate.label;
  assignSampleToActiveSite(sample);
  renderSearchResults(candidates);
  searchStatus.textContent = `placed Site ${targetSite} from ${candidate.source}`;
}

async function sampleTerrainHeight(lon, lat) {
  if (!useWorldTerrain) {
    return 0;
  }

  try {
    const [sample] = await Cesium.sampleTerrainMostDetailed(
      viewer.terrainProvider,
      [Cesium.Cartographic.fromDegrees(lon, lat)]
    );
    return sample.height || 0;
  } catch (_error) {
    return 0;
  }
}
