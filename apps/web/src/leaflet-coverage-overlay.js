import L from "leaflet";
import { loadProviderCoverageCache, saveProviderCoverageCache } from "./provider-coverage-cache.js";
import { coverageShouldShow } from "./provider-selection.js";

const BKG_STATE_BOUNDARY_URL = "https://sgx.geodatenzentrum.de/wfs_vg250?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=vg250:vg250_lan&outputFormat=application%2Fjson&SRSNAME=EPSG%3A4326&COUNT=20";

/**
 * Returns { loadProviderCoverage, updateCoverageOverlay } bound to the given
 * map, state, and DOM elements. Call once after all five arguments are ready.
 */
export function createCoverageOverlay(map, state, providerCoverage, coverageToggle, downloadStatus) {
  function updateCoverageOverlay() {
    for (const [provider, layer] of Object.entries(state.coverageLayers)) {
      const shouldShow = coverageShouldShow(state.provider, provider, coverageToggle.checked);
      if (shouldShow && !map.hasLayer(layer)) layer.addTo(map);
      if (!shouldShow && map.hasLayer(layer)) map.removeLayer(layer);
    }
  }

  function applyProviderCoverage(featuresByProvider) {
    for (const layer of Object.values(state.coverageLayers)) {
      if (map.hasLayer(layer)) map.removeLayer(layer);
    }
    state.coverageLayers = {};
    state.coverageFeatures = {};
    for (const [provider, feature] of Object.entries(featuresByProvider)) {
      const config = providerCoverage[provider];
      if (!config) continue;
      state.coverageLayers[provider] = L.geoJSON(feature, {
        style: { color: config.color, weight: 2, fillColor: config.color, fillOpacity: 0.12 },
      });
      state.coverageFeatures[provider] = feature;
    }
    updateCoverageOverlay();
  }

  async function loadProviderCoverage() {
    const cachedFeatures = loadProviderCoverageCache();
    if (cachedFeatures) {
      applyProviderCoverage(cachedFeatures);
    }
    try {
      const response = await fetch(BKG_STATE_BOUNDARY_URL);
      if (!response.ok) throw new Error("Boundary service unavailable");
      const collection = await response.json();
      const featuresByProvider = {};
      for (const [provider, config] of Object.entries(providerCoverage)) {
        const feature = collection.features.find((c) => c.properties.lkz === config.stateCode);
        if (feature) featuresByProvider[provider] = feature;
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

  return { loadProviderCoverage, updateCoverageOverlay };
}
