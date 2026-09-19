import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import "./maplibre-prototype.css";
import { renderMapLibreShell } from "./maplibre-prototype-shell.js";
import { mapStyle } from "./maplibre-prototype-style.js";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? window.location.origin).trim();
const params = new URLSearchParams(window.location.search);
const variant = params.get("variant") || "corridor";
const baseLayerIds = [
  "osm",
  "nrw-dop",
  "nrw-topo",
  "nrw-dtm",
  "nrw-dhm-overview",
  "nrw-ndom50-wms",
  "nrw-dom1-local",
  "nrw-dgm1-local",
  "nrw-ndsm-local",
];
const domSourceId = "nrw-dom1-local";

document.getElementById("app").innerHTML = renderMapLibreShell(variant);

const elements = {
  baseLayerSelect: document.getElementById("baseLayerSelect"),
  activeLayerOpacity: document.getElementById("activeLayerOpacity"),
  activeLayerOpacityReadout: document.getElementById("activeLayerOpacityReadout"),
  domOverlayEnabled: document.getElementById("domOverlayEnabled"),
  domOverlayOpacity: document.getElementById("domOverlayOpacity"),
  domOverlayOpacityReadout: document.getElementById("domOverlayOpacityReadout"),
  probeTargetSelect: document.getElementById("probeTargetSelect"),
  probeEnabled: document.getElementById("probeEnabled"),
  probeSampleButton: document.getElementById("probeSampleButton"),
  probeReadout: document.getElementById("probeReadout"),
  layerStatus: document.getElementById("layerStatus"),
  mapStatus: document.getElementById("mapStatus"),
  resetDomMetricsButton: document.getElementById("resetDomMetricsButton"),
};

const state = {
  currentBaseLayer: elements.baseLayerSelect.value,
  domMetrics: emptyDomMetrics(),
  hoverSample: null,
  probe: {
    enabled: true,
    mode: "hover",
    target: "combined",
    status: "idle",
    result: null,
    error: "",
  },
};
let probeTimerId = 0;
let probeRequestId = 0;

const map = new maplibregl.Map({
  container: "maplibreMap",
  style: mapStyle(apiBaseUrl),
  center: [7.47, 51.43],
  zoom: 8,
  attributionControl: true,
  collectResourceTiming: true,
});

map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-left");
map.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 140 }), "bottom-left");

bindEvents();
renderOpacityReadout();
renderDomOverlayReadout();
renderProbeReadout();
renderLayerStatus();

function bindEvents() {
  bindMapEvents();
  bindLayerControlEvents();
  bindProbeControlEvents();
  bindDomMetricControls();
}

function bindMapEvents() {
  map.on("load", () => {
    elements.mapStatus.textContent = "Map ready.";
    updateBaseLayerVisibility();
    updateActiveLayerOpacity();
    updateDomOverlay();
    renderLayerStatus();
  });
  map.on("mousemove", (event) => handlePointerMove(event.lngLat));
  map.on("click", (event) => handleMapClick(event.lngLat));
  map.on("error", (event) => {
    const message = event?.error?.message || "MapLibre error";
    elements.mapStatus.textContent = message;
  });
  map.on("sourcedataloading", (event) => {
    if (!isDomSourceEvent(event)) return;
    startDomBatch();
    state.domMetrics.started += 1;
    state.domMetrics.pending += 1;
    state.domMetrics.lastActivityAt = performance.now();
    renderLayerStatus();
  });
  map.on("sourcedata", (event) => {
    if (!isDomSourceEvent(event)) return;
    if (state.domMetrics.pending > 0) {
      state.domMetrics.pending -= 1;
    }
    state.domMetrics.completed += 1;
    state.domMetrics.lastActivityAt = performance.now();
    finishDomBatchIfReady();
    renderLayerStatus();
  });
  map.on("idle", () => {
    finishDomBatchIfReady();
    renderLayerStatus();
  });
}

function bindLayerControlEvents() {
  elements.baseLayerSelect.addEventListener("change", () => {
    state.currentBaseLayer = elements.baseLayerSelect.value;
    updateBaseLayerVisibility();
    updateActiveLayerOpacity();
    updateDomOverlay();
    renderLayerStatus();
  });
  elements.activeLayerOpacity.addEventListener("input", () => {
    updateActiveLayerOpacity();
    renderOpacityReadout();
  });
  elements.activeLayerOpacity.addEventListener("change", () => {
    updateActiveLayerOpacity();
    renderOpacityReadout();
  });
  elements.domOverlayEnabled.addEventListener("change", updateDomOverlay);
  elements.domOverlayOpacity.addEventListener("input", () => {
    updateDomOverlay();
    renderDomOverlayReadout();
  });
  elements.domOverlayOpacity.addEventListener("change", () => {
    updateDomOverlay();
    renderDomOverlayReadout();
  });
}

function bindProbeControlEvents() {
  elements.probeTargetSelect.addEventListener("change", () => {
    state.probe.target = elements.probeTargetSelect.value;
    state.probe.result = null;
    state.probe.error = "";
    renderProbeReadout();
    queueProbe();
  });
  elements.probeEnabled.addEventListener("change", () => {
    state.probe.enabled = elements.probeEnabled.checked;
    if (!state.probe.enabled) {
      state.probe.status = "idle";
      state.probe.result = null;
      state.probe.error = "";
    }
    renderProbeReadout();
  });
  for (const input of document.querySelectorAll('input[name="probeMode"]')) {
    input.addEventListener("change", handleProbeModeChange);
  }
  elements.probeSampleButton.addEventListener("click", handleManualProbeSample);
}

function bindDomMetricControls() {
  elements.resetDomMetricsButton.addEventListener("click", () => {
    state.domMetrics = emptyDomMetrics();
    renderLayerStatus();
  });
}

function updateBaseLayerVisibility() {
  for (const layerId of baseLayerIds) {
    map.setLayoutProperty(layerId, "visibility", layerId === state.currentBaseLayer ? "visible" : "none");
  }
  elements.mapStatus.textContent = layerStatusText(state.currentBaseLayer);
}

function updateActiveLayerOpacity() {
  const opacity = Number(elements.activeLayerOpacity.value);
  map.setPaintProperty(state.currentBaseLayer, "raster-opacity", opacity);
}

function renderOpacityReadout() {
  elements.activeLayerOpacityReadout.textContent = `${Math.round(Number(elements.activeLayerOpacity.value) * 100)}%`;
}

function renderDomOverlayReadout() {
  elements.domOverlayOpacityReadout.textContent = `${Math.round(Number(elements.domOverlayOpacity.value) * 100)}%`;
}

function renderLayerStatus() {
  elements.layerStatus.textContent = layerStatusText(state.currentBaseLayer, state.domMetrics);
}

function layerStatusText(layerId, metrics) {
  if (layerId === domSourceId) return domLayerStatusText(metrics);
  const staticStatus = staticLayerStatusText(layerId);
  if (staticStatus) return staticStatus;
  return `Active layer: ${elements.baseLayerSelect.selectedOptions[0]?.textContent || layerId}`;
}

function domLayerStatusText(metrics) {
  const inFlightMs = metrics.batchStartedAt ? Math.round(performance.now() - metrics.batchStartedAt) : 0;
  const lastBatchMs = metrics.lastBatchDurationMs === null ? "n/a" : `${Math.round(metrics.lastBatchDurationMs)} ms`;
  return [
    "Active layer: NRW DOM1 local",
    `URL template: ${apiBaseUrl}/api/v1/tiles/geobasis-nrw/dom1/{z}/{x}/{y}.png`,
    `Tiles started: ${metrics.started}`,
    `Tiles completed: ${metrics.completed}`,
    `Tiles pending: ${metrics.pending}`,
    `Current batch age: ${metrics.batchStartedAt ? `${inFlightMs} ms` : "n/a"}`,
    `Last batch duration: ${lastBatchMs}`,
  ].join("\n");
}

function staticLayerStatusText(layerId) {
  const statuses = {
    "nrw-dgm1-local": [
      "Active layer: NRW DGM1 local",
      `URL template: ${apiBaseUrl}/api/v1/tiles/geobasis-nrw/dgm1/{z}/{x}/{y}.png`,
      "Meaning: bare-earth terrain raster.",
    ],
    "nrw-ndsm-local": [
      "Active layer: NRW nDSM local",
      `URL template: ${apiBaseUrl}/api/v1/tiles/geobasis-nrw/ndsm/{z}/{x}/{y}.png`,
      "Meaning: DOM1 minus DGM1. Bare ground should be near 0.",
    ],
    "nrw-ndom50-wms": [
      "Active layer: NRW nDOM50 WMS",
      "Service: https://www.wms.nrw.de/geobasis/wms_nw_ndom",
      "Meaning: hosted relative-height display layer. Visual only in this prototype.",
    ],
    "nrw-dhm-overview": [
      "Active layer: NRW DHM overview WMS",
      "Service: https://www.wms.nrw.de/geobasis/wms_nw_dhm-uebersicht",
      "Meaning: hosted overview layer, not the DOM WCS service.",
    ],
  };
  return statuses[layerId]?.join("\n") || "";
}

function updateDomOverlay() {
  const opacity = Number(elements.domOverlayOpacity.value);
  const enabled = elements.domOverlayEnabled.checked && state.currentBaseLayer === "nrw-dop";
  map.setLayoutProperty("nrw-dom1-hillshade-local", "visibility", enabled ? "visible" : "none");
  map.setPaintProperty("nrw-dom1-hillshade-local", "raster-opacity", opacity);
  elements.domOverlayEnabled.disabled = state.currentBaseLayer !== "nrw-dop";
}

function handlePointerMove(lngLat) {
  state.hoverSample = { lat: lngLat.lat, lon: lngLat.lng };
  if (!state.probe.enabled) return;
  if (state.probe.mode === "hover") queueProbe();
  else renderProbeReadout();
}

function handleMapClick(lngLat) {
  state.hoverSample = { lat: lngLat.lat, lon: lngLat.lng };
  if (state.probe.enabled && state.probe.mode === "manual") {
    void fetchProbe(state.hoverSample, ++probeRequestId);
  } else {
    renderProbeReadout();
  }
}

function handleProbeModeChange(event) {
  if (!(event.target instanceof HTMLInputElement) || !event.target.checked) return;
  state.probe.mode = event.target.value;
  state.probe.status = "idle";
  state.probe.error = "";
  renderProbeReadout();
  queueProbe();
}

function handleManualProbeSample() {
  if (!state.probe.enabled || !state.hoverSample) {
    state.probe.error = "Move the cursor over a point first.";
    renderProbeReadout();
    return;
  }
  void fetchProbe(state.hoverSample, ++probeRequestId);
}

function queueProbe() {
  if (!state.probe.enabled || state.probe.mode !== "hover" || !state.hoverSample) return;
  if (probeTimerId) window.clearTimeout(probeTimerId);
  probeTimerId = window.setTimeout(() => {
    probeTimerId = 0;
    void fetchProbe(state.hoverSample, ++probeRequestId);
  }, 180);
}

async function fetchProbe(sample, requestId) {
  state.probe.status = "loading";
  state.probe.error = "";
  renderProbeReadout();
  try {
    const result = state.probe.target === "combined"
      ? await requestCombinedProbe(sample)
      : await requestSingleProbe(sample, state.probe.target);
    if (requestId !== probeRequestId) return;
    state.probe.status = "ready";
    state.probe.result = result;
  } catch (error) {
    if (requestId !== probeRequestId) return;
    state.probe.status = "error";
    state.probe.result = null;
    state.probe.error = error instanceof Error ? error.message : "Probe failed";
  }
  renderProbeReadout();
}

async function requestCombinedProbe(sample) {
  const response = await fetch(`${apiBaseUrl}/api/v1/probe/multi`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider: "geobasis-nrw", lon: sample.lon, lat: sample.lat }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "Combined probe failed");
  return payload;
}

async function requestSingleProbe(sample, dataset) {
  const response = await fetch(`${apiBaseUrl}/api/v1/probe/point`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider: "geobasis-nrw", dataset, lon: sample.lon, lat: sample.lat }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "Probe failed");
  return payload;
}

function renderProbeReadout() {
  if (!state.probe.enabled) {
    elements.probeReadout.textContent = "Probe disabled.";
    return;
  }
  if (!state.hoverSample) {
    elements.probeReadout.textContent = state.probe.mode === "manual"
      ? "Manual mode: click the map or use Sample now."
      : "Move over the map to read DGM, DOM, and nDSM.";
    return;
  }
  const lines = [
    `Lat ${state.hoverSample.lat.toFixed(6)}`,
    `Lon ${state.hoverSample.lon.toFixed(6)}`,
    `Mode ${state.probe.mode}`,
    `Target ${probeTargetLabel(state.probe.target)}`,
  ];
  if (state.probe.status === "loading") {
    lines.push("Probe loading...");
  } else if (state.probe.status === "error") {
    lines.push(`Probe error: ${state.probe.error}`);
  } else if (state.probe.status === "ready" && state.probe.result) {
    appendProbeValues(lines, state.probe.target, state.probe.result);
  } else {
    lines.push("Probe not sampled yet.");
  }
  elements.probeReadout.textContent = lines.join("\n");
}

function appendProbeValues(lines, target, result) {
  if (target === "combined") {
    lines.push(formatProbeValue("DGM1", result.dgm_m, result.dgm_error));
    lines.push(formatProbeValue("DOM1", result.dom_m, result.dom_error));
    lines.push(formatProbeValue("nDSM", result.ndsm_m, null));
    return;
  }
  lines.push(formatProbeValue(target.toUpperCase(), result.height_m, null));
}

function formatProbeValue(label, value, error) {
  if (error) return `${label}: ${error}`;
  if (typeof value !== "number") return `${label}: n/a`;
  return `${label}: ${value.toFixed(2)} m`;
}

function probeTargetLabel(target) {
  if (target === "combined") return "DGM1 + DOM1 + nDSM";
  if (target === "dgm1") return "DGM1";
  if (target === "dom1") return "DOM1";
  return "nDSM";
}

function renderDomMetrics() {
  const metrics = state.domMetrics;
  const visible = state.currentBaseLayer === domSourceId ? "yes" : "no";
  const inFlightMs = metrics.batchStartedAt ? Math.round(performance.now() - metrics.batchStartedAt) : 0;
  const lastBatchMs = metrics.lastBatchDurationMs === null ? "n/a" : `${Math.round(metrics.lastBatchDurationMs)} ms`;
  elements.layerStatus.textContent = [
    `Visible as active layer: ${visible}`,
    `Source id: ${domSourceId}`,
    `URL template: ${apiBaseUrl}/api/v1/tiles/geobasis-nrw/dom1/{z}/{x}/{y}.png`,
    `Current batch started: ${metrics.batchStartedAt ? "yes" : "no"}`,
    `Tiles started: ${metrics.started}`,
    `Tiles completed: ${metrics.completed}`,
    `Tiles pending: ${metrics.pending}`,
    `Current batch age: ${metrics.batchStartedAt ? `${inFlightMs} ms` : "n/a"}`,
    `Last batch duration: ${lastBatchMs}`,
  ].join("\n");
  if (visible === "yes" && !metrics.batchStartedAt && metrics.completed === 0) {
    elements.mapStatus.textContent = "DOM layer selected. Pan or zoom to trigger tile fetches.";
  }
}

function startDomBatch() {
  if (state.domMetrics.batchStartedAt) return;
  state.domMetrics.batchStartedAt = performance.now();
}

function finishDomBatchIfReady() {
  const metrics = state.domMetrics;
  if (!metrics.batchStartedAt || metrics.pending > 0) return;
  metrics.lastBatchDurationMs = performance.now() - metrics.batchStartedAt;
  metrics.batchStartedAt = 0;
}

function isDomSourceEvent(event) {
  return event?.sourceId === domSourceId;
}

function emptyDomMetrics() {
  return {
    batchStartedAt: 0,
    started: 0,
    completed: 0,
    pending: 0,
    lastBatchDurationMs: null,
    lastActivityAt: 0,
  };
}
