import "cesium/Build/Cesium/Widgets/widgets.css";
import "./style.css";
import * as Cesium from "cesium";

window.CESIUM_BASE_URL = "/node_modules/cesium/Build/Cesium";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").trim();
const cesiumIonToken = (import.meta.env.VITE_CESIUM_ION_TOKEN || "").trim();
const useWorldTerrain = (import.meta.env.VITE_USE_WORLD_TERRAIN || "false").trim().toLowerCase() === "true";

if (cesiumIonToken) {
  Cesium.Ion.defaultAccessToken = cesiumIonToken;
}

const app = document.getElementById("app");

app.innerHTML = `
  <div class="shell">
    <aside class="panel panel-left">
      <div class="eyebrow">MultiPlanner</div>
      <h1>Local-first terrain planning</h1>
      <p class="lede">
        First cut: place two sites, keep the UI local, and wire the map shell to
        the backend contracts that will later drive subset fetch and LOS.
      </p>
      <div class="actions">
        <button id="btnSiteA">Mark Site A</button>
        <button id="btnSiteB">Mark Site B</button>
        <button id="btnCenter" class="button-ghost">Center active site</button>
        <button id="btnClear" class="button-ghost">Clear</button>
      </div>
      <div class="search-panel">
        <label class="field-label" for="searchInput">Search place or coordinates</label>
        <div class="search-row">
          <input id="searchInput" type="text" placeholder="52.324784, 7.467435 or street, city, business" />
          <button id="btnSearch" class="button-ghost">Find</button>
        </div>
        <div id="searchStatus" class="lookup-status">search will place the active site</div>
        <div id="searchResults" class="search-results"></div>
      </div>
      <dl class="facts">
        <div>
          <dt>API</dt>
          <dd id="apiStatus">checking</dd>
        </div>
        <div>
          <dt>Provider mode</dt>
          <dd id="providerMode">loading</dd>
        </div>
        <div>
          <dt>Selection</dt>
          <dd id="selectionMode">Site A</dd>
        </div>
        <div>
          <dt>Terrain mode</dt>
          <dd id="terrainMode">${useWorldTerrain ? "world terrain" : "fast local"}</dd>
        </div>
      </dl>
      <div class="site-readout">
        <div>
          <span>Site A</span>
          <strong id="siteAValue">not set</strong>
        </div>
        <div>
          <span>Site B</span>
          <strong id="siteBValue">not set</strong>
        </div>
      </div>
    </aside>
    <section class="map-stage">
      <div id="cesiumContainer"></div>
      <div class="hud">
        <div class="hud-card">
          <div class="hud-label">Next build target</div>
          <div class="hud-value">subset fetch + LOS</div>
        </div>
        <div class="hud-card">
          <div class="hud-label">Backend</div>
          <div class="hud-value">FastAPI localhost</div>
        </div>
      </div>
    </section>
  </div>
`;

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

if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    viewer.destroy();
  });
}

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

const lookupPanel = document.createElement("div");
lookupPanel.className = "lookup-panel";
lookupPanel.innerHTML = `
  <button id="btnLocate" class="button-ghost">Preview corridor subsets</button>
  <button id="btnDownload" class="button-ghost">Keep subset tiles</button>
  <div id="lookupStatus" class="lookup-status">waiting for two sites</div>
`;
document.querySelector(".panel-left").appendChild(lookupPanel);

const btnLocate = document.getElementById("btnLocate");
const btnDownload = document.getElementById("btnDownload");
const lookupStatus = document.getElementById("lookupStatus");

const state = {
  selectionMode: "A",
  siteA: null,
  siteB: null,
  siteAEntity: null,
  siteBEntity: null,
  linkEntity: null,
  apiReady: false,
  lastSelectedSearchLabel: null
};

btnSiteA.addEventListener("click", () => setSelectionMode("A"));
btnSiteB.addEventListener("click", () => setSelectionMode("B"));
btnCenter.addEventListener("click", centerActiveSite);
btnClear.addEventListener("click", clearSelections);
btnSearch.addEventListener("click", runSearch);
btnLocate.addEventListener("click", locateCorridorSubsets);
btnDownload.addEventListener("click", downloadCorridorSubsets);
searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    runSearch();
  }
});

const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
handler.setInputAction((movement) => {
  const sample = pickSampleFromScreen(movement.position);
  if (!sample) {
    return;
  }

  assignSampleToActiveSite(sample);
}, Cesium.ScreenSpaceEventType.LEFT_CLICK);

setSelectionMode("A");
updateReadout();
bootstrapApiState();

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

function pickSampleFromScreen(screenPosition) {
  let cartesian = null;

  if (useWorldTerrain && viewer.scene.pickPositionSupported) {
    cartesian = viewer.scene.pickPosition(screenPosition);
  }

  if (!Cesium.defined(cartesian)) {
    cartesian = viewer.camera.pickEllipsoid(screenPosition, viewer.scene.globe.ellipsoid);
  }

  if (!Cesium.defined(cartesian)) {
    return null;
  }

  const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
  return {
    lon: Cesium.Math.toDegrees(cartographic.longitude),
    lat: Cesium.Math.toDegrees(cartographic.latitude),
    height: cartographic.height || 0
  };
}

function upsertSite(kind, sample) {
  const id = kind === "A" ? "site-a" : "site-b";
  const color = kind === "A" ? Cesium.Color.CYAN : Cesium.Color.ORANGE;
  const existing = kind === "A" ? state.siteAEntity : state.siteBEntity;

  if (existing) {
    existing.position = Cesium.Cartesian3.fromDegrees(sample.lon, sample.lat, sample.height);
    existing.label.text = siteLabel(kind, sample);
    return;
  }

  const entity = viewer.entities.add({
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

  if (kind === "A") {
    state.siteAEntity = entity;
  } else {
    state.siteBEntity = entity;
  }
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
    polyline: {
      positions: Cesium.Cartesian3.fromDegreesArrayHeights([
        state.siteA.lon,
        state.siteA.lat,
        state.siteA.height,
        state.siteB.lon,
        state.siteB.lat,
        state.siteB.height
      ]),
      width: 3,
      material: Cesium.Color.LIME
    }
  });
}

function siteLabel(kind, sample) {
  return `${kind}: ${sample.lon.toFixed(5)}, ${sample.lat.toFixed(5)}`;
}

function updateReadout() {
  siteAValue.textContent = state.siteA ? formatSample(state.siteA) : "not set";
  siteBValue.textContent = state.siteB ? formatSample(state.siteB) : "not set";
  btnLocate.disabled = !(state.siteA && state.siteB);
  btnDownload.disabled = !(state.siteA && state.siteB);
  if (!(state.siteA && state.siteB)) {
    lookupStatus.textContent = "waiting for two sites";
  }
}

function formatSample(sample) {
  return `${sample.lon.toFixed(5)}, ${sample.lat.toFixed(5)} @ ${sample.height.toFixed(1)} m`;
}

async function bootstrapApiState() {
  terrainModeEl.textContent = useWorldTerrain ? "world terrain" : "fast local";
  apiStatus.textContent = "starting";
  providerMode.textContent = "waiting for backend";
  for (let attempt = 1; attempt <= 12; attempt += 1) {
    try {
      const [healthResponse, configResponse] = await Promise.all([
        fetchWithTimeout(`${apiBaseUrl}/healthz`, { timeoutMs: 2000 }),
        fetchWithTimeout(`${apiBaseUrl}/api/v1/config`, { timeoutMs: 2000 })
      ]);

      if (!healthResponse.ok || !configResponse.ok) {
        throw new Error("API bootstrap failed");
      }

      const health = await healthResponse.json();
      const config = await configResponse.json();
      apiStatus.textContent = health.status;
      providerMode.textContent = config.provider_mode;
      state.apiReady = true;
      return;
    } catch (_error) {
      apiStatus.textContent = attempt < 12 ? "starting" : "offline";
      providerMode.textContent = attempt < 12 ? "waiting for backend" : "unavailable";
      await delay(1000);
    }
  }
}

function delay(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
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
    const response = await fetchWithTimeout(
      `${apiBaseUrl}/api/v1/search/places?q=${encodeURIComponent(query)}`,
      { timeoutMs: 5000 }
    );
    if (!response.ok) {
      throw new Error("search failed");
    }

    const payload = await response.json();
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

async function locateCorridorSubsets() {
  if (!state.apiReady) {
    lookupStatus.textContent = "backend still starting";
    return;
  }

  if (!(state.siteA && state.siteB)) {
    lookupStatus.textContent = "set both sites first";
    return;
  }

  lookupStatus.textContent = "querying provider";
  try {
    const response = await fetchWithTimeout(`${apiBaseUrl}/api/v1/subsets/locate`, {
      method: "POST",
      timeoutMs: 10000,
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        provider: "lgln-ni",
        datasets: ["dgm1", "dom1", "dop20"],
        geometry: {
          kind: "corridor",
          from_lon: state.siteA.lon,
          from_lat: state.siteA.lat,
          to_lon: state.siteB.lon,
          to_lat: state.siteB.lat,
          buffer_m: 75
        }
      })
    });

    if (!response.ok) {
      throw new Error("subset lookup failed");
    }

    const payload = await response.json();
    const summary = payload.results
      .map((entry) => `${entry.dataset}: ${entry.match_count}`)
      .join(" | ");
    lookupStatus.textContent = summary || "no subset matches";
  } catch (_error) {
    lookupStatus.textContent = "subset lookup failed";
  }
}

async function downloadCorridorSubsets() {
  if (!state.apiReady) {
    lookupStatus.textContent = "backend still starting";
    return;
  }

  if (!(state.siteA && state.siteB)) {
    lookupStatus.textContent = "set both sites first";
    return;
  }

  lookupStatus.textContent = "downloading selected subset tiles";
  try {
    const response = await fetchWithTimeout(`${apiBaseUrl}/api/v1/subsets/download`, {
      method: "POST",
      timeoutMs: 30000,
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        provider: "lgln-ni",
        datasets: ["dgm1", "dom1", "dop20"],
        selection_name: buildSelectionName(),
        export_profile: "ellipse_mapinfo_tab",
        geometry: {
          kind: "corridor",
          from_lon: state.siteA.lon,
          from_lat: state.siteA.lat,
          to_lon: state.siteB.lon,
          to_lat: state.siteB.lat,
          buffer_m: 75
        }
      })
    });

    if (!response.ok) {
      throw new Error("subset download failed");
    }

    const payload = await response.json();
    const exportHint = payload.exports.length ? ` | ellipse exports: ${payload.exports.length}` : "";
    lookupStatus.textContent = `saved ${payload.file_count} files to ${payload.output_dir}${exportHint}`;
  } catch (_error) {
    lookupStatus.textContent = "subset download failed";
  }
}

function buildSelectionName() {
  if (!(state.siteA && state.siteB)) {
    return "subset";
  }
  return `corridor_${state.siteA.lon.toFixed(3)}_${state.siteA.lat.toFixed(3)}_${state.siteB.lon.toFixed(3)}_${state.siteB.lat.toFixed(3)}`;
}
