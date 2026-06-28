// Leaflet NRW probe prototype — reuses the same API endpoints as the MapLibre
// prototype: /api/v1/tiles/geobasis-nrw/{dataset}/{z}/{x}/{y}.png for raster
// overlays, and /api/v1/probe/multi + /api/v1/probe/point for elevation reads.
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./leaflet-nrw-probe.css";
import { renderNrwProbeShell, panelRefs } from "./leaflet-nrw-probe-panel.js";

const API = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").trim();
const PROVIDER = "geobasis-nrw";
const NRW_CENTER = [51.43, 7.66];
const NRW_ZOOM = 13;
const HOVER_DELAY_MS = 400;

document.getElementById("app").innerHTML = renderNrwProbeShell();
const refs = panelRefs();
const map = L.map("nrwMap", { zoomControl: true }).setView(NRW_CENTER, NRW_ZOOM);

// --- Layer instances ---
const _localTile = (ds) =>
  L.tileLayer(`${API}/api/v1/tiles/${PROVIDER}/${ds}/{z}/{x}/{y}.png`, { maxZoom: 20 });

const BASE_LAYERS = {
  dop: L.tileLayer.wms("https://www.wms.nrw.de/geobasis/wms_nw_dop", {
    layers: "nw_dop_rgb",
    format: "image/jpeg",
    transparent: false,
    maxZoom: 20,
    attribution: "© Geobasis NRW",
  }),
  dgm1: _localTile("dgm1"),
  dom1: _localTile("dom1"),
  ndsm: _localTile("ndsm"),
  streets: L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors",
    maxZoom: 20,
  }),
};

// Official NRW normalised surface model (relative height above terrain).
const NDOM_OVERLAY = L.tileLayer.wms("https://www.wms.nrw.de/geobasis/wms_nw_ndom", {
  layers: "nw_ndom",
  format: "image/png",
  transparent: true,
  opacity: 0.6,
  maxZoom: 20,
  attribution: "© Geobasis NRW",
});

// --- Mutable state ---
let currentBase = BASE_LAYERS.dop;
let hoverTimer = null;
let lastLatlng = null;
let probeEnabled = false;

currentBase.addTo(map);

// --- Layer management ---
function switchBase(key) {
  map.removeLayer(currentBase);
  currentBase = BASE_LAYERS[key];
  currentBase.setOpacity(refs.baseOpacity.value / 100);
  currentBase.addTo(map);
  if (map.hasLayer(NDOM_OVERLAY)) NDOM_OVERLAY.bringToFront();
}

function setBaseOpacity(pct) {
  currentBase.setOpacity(pct / 100);
  refs.baseOpacityVal.textContent = `${pct}%`;
}

function toggleNdomOverlay(enabled) {
  if (enabled) {
    NDOM_OVERLAY.addTo(map);
  } else {
    map.removeLayer(NDOM_OVERLAY);
  }
}

function setNdomOpacity(pct) {
  NDOM_OVERLAY.setOpacity(pct / 100);
  refs.ndomOpacityVal.textContent = `${pct}%`;
}

// --- Probe ---
async function probe(latlng) {
  if (!probeEnabled) return;
  lastLatlng = latlng;
  const source = refs.probeSource.value;
  refs.probeResult.textContent = `Probing ${latlng.lat.toFixed(6)}, ${latlng.lng.toFixed(6)}…`;
  try {
    const result = await _fetchProbe(source, latlng.lat, latlng.lng);
    refs.probeResult.textContent = _formatResult(result, source, latlng.lat, latlng.lng);
  } catch (err) {
    refs.probeResult.textContent = `Error: ${err.message}`;
  }
}

async function _fetchProbe(source, lat, lon) {
  if (source === "multi") {
    return _postJson(`${API}/api/v1/probe/multi`, { provider: PROVIDER, lat, lon });
  }
  return _postJson(`${API}/api/v1/probe/point`, { provider: PROVIDER, dataset: source, lat, lon });
}

async function _postJson(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? r.statusText);
  return r.json();
}

function _probeMode() {
  return document.querySelector('input[name="nrwProbeMode"]:checked')?.value ?? "manual";
}

function _formatResult(r, source, lat, lon) {
  const fmt = (v) => (v != null ? `${v.toFixed(2)} m` : "—");
  const target = source === "multi" ? "DGM1 + DOM1 + nDSM" : source.toUpperCase();
  const lines = [`Lat ${lat.toFixed(6)}`, `Lon ${lon.toFixed(6)}`, `Mode ${_probeMode()}`, `Target ${target}`];
  if (source === "multi") {
    lines.push(`DGM1:  ${fmt(r.dgm_m)}`, `DOM1:  ${fmt(r.dom_m)}`, `nDSM:  ${fmt(r.ndsm_m)}`);
  } else {
    lines.push(`${source.toUpperCase()}:  ${fmt(r.height_m)}`);
  }
  return lines.join("\n");
}

// --- Event wiring ---
refs.layerSelect.addEventListener("change", () => switchBase(refs.layerSelect.value));
refs.baseOpacity.addEventListener("input", () => setBaseOpacity(Number(refs.baseOpacity.value)));
refs.ndomOverlay.addEventListener("change", () => toggleNdomOverlay(refs.ndomOverlay.checked));
refs.ndomOpacity.addEventListener("input", () => setNdomOpacity(Number(refs.ndomOpacity.value)));

refs.probeEnable.addEventListener("change", () => {
  probeEnabled = refs.probeEnable.checked;
  map.getContainer().classList.toggle("nrw-probe-cursor", probeEnabled);
  if (!probeEnabled) refs.probeResult.textContent = "";
});

refs.sampleNow.addEventListener("click", () => {
  if (lastLatlng) probe(lastLatlng);
});

map.on("click", (e) => {
  if (probeEnabled && _probeMode() === "manual") probe(e.latlng);
  else if (probeEnabled) lastLatlng = e.latlng;
});

map.on("mousemove", (e) => {
  if (!probeEnabled || _probeMode() !== "hover") return;
  lastLatlng = e.latlng;
  clearTimeout(hoverTimer);
  hoverTimer = setTimeout(() => probe(e.latlng), HOVER_DELAY_MS);
});
