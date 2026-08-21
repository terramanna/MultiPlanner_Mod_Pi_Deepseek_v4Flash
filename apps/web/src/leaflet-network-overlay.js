import L from "leaflet";

const LINK_COLORS = {
  "30_Primary": "#1d4ed8",
  "20_Nominal": "#8b4513",
};
const OTHER_LINK_COLOR = "#6b7280";

const _SEARCH_FIELDS = ["name", "name2", "site_a", "site_b", "s_number", "s_number_a", "s_number_b"];

// createNetworkOverlay — manages site + link GeoJSON layers on the Leaflet map.
// Two independent groups can be toggled, mirroring NSP_UBT: "primary_nominal"
// (Primary/Nominal links) and "other" (every other active link state).
// callbacks: { onSiteA(props), onSiteB(props), onCorridor(props) }
export function createNetworkOverlay(map, apiBaseUrl, callbacks) {
  const state = {
    allFeatures: [],
    sitesLayer: null,
    linksLayer: null,
    loaded: false,
    loadingPromise: null,
    lastQuery: "",
    enabledGroups: new Set(),
  };

  async function enable(group) {
    state.enabledGroups.add(group);
    await _ensureLoaded(state, apiBaseUrl);
    _render(map, state, callbacks);
  }

  function disable(group) {
    state.enabledGroups.delete(group);
    if (state.enabledGroups.size === 0) {
      state.sitesLayer?.remove();
      state.linksLayer?.remove();
      return;
    }
    _render(map, state, callbacks);
  }

  function filter(query) {
    state.lastQuery = query;
    if (state.loaded) _render(map, state, callbacks);
  }

  return { enable, disable, filter };
}

async function _ensureLoaded(state, apiBaseUrl) {
  if (state.loaded) return;
  state.loadingPromise ??= _fetchGeoJSON(apiBaseUrl).then((fc) => {
    state.allFeatures = fc.features ?? [];
    state.loaded = true;
  });
  await state.loadingPromise;
}

function _render(map, state, callbacks) {
  state.sitesLayer?.remove();
  state.linksLayer?.remove();
  const q = state.lastQuery.trim().toLowerCase();
  const links = state.allFeatures.filter(
    (f) => f.properties.layer === "link" && state.enabledGroups.has(f.properties.group) && (!q || _matches(f, q))
  );
  const sites = state.allFeatures.filter(
    (f) => f.properties.layer === "site" && _siteGroupVisible(state.enabledGroups, f.properties) && (!q || _matches(f, q))
  );
  state.linksLayer = _buildLinksLayer(links, callbacks).addTo(map);
  state.sitesLayer = _buildSitesLayer(sites, callbacks).addTo(map);
}

function _siteGroupVisible(enabledGroups, props) {
  return (
    (enabledGroups.has("primary_nominal") && props.has_primary_nominal) ||
    (enabledGroups.has("other") && props.has_other)
  );
}

function _matches(feature, q) {
  return _SEARCH_FIELDS.some((field) => feature.properties[field]?.toLowerCase().includes(q));
}

async function _fetchGeoJSON(apiBaseUrl) {
  const resp = await fetch(`${apiBaseUrl}/api/v1/network/geojson`);
  if (!resp.ok) throw new Error(`Network overlay: ${resp.status}`);
  return resp.json();
}

function _buildLinksLayer(features, callbacks) {
  return L.geoJSON(features, {
    style: (f) => ({
      color: LINK_COLORS[f.properties.state] ?? OTHER_LINK_COLOR,
      weight: 2,
      opacity: 0.85,
    }),
    onEachFeature: (feature, layer) => {
      layer.on("click", (event) => _openLinkPopup(layer, feature.properties, callbacks, event.latlng));
    },
  });
}

function _buildSitesLayer(features, callbacks) {
  return L.geoJSON(features, {
    pointToLayer: (_f, latlng) =>
      L.circleMarker(latlng, { radius: 5, color: "#1e3a5f", fillColor: "#3b82f6", fillOpacity: 0.85, weight: 1 }),
    onEachFeature: (feature, layer) => {
      layer.on("click", () => _openSitePopup(layer, feature.properties, callbacks));
    },
  });
}

function _v(value) { return value || "—"; }

function _opt(label, value) { return value ? `<br/>${label}: ${value}` : ""; }

function _sideHtml(site, snum, ellipseStatus, trackerStatus) {
  const suffix = snum ? ` (${snum})` : "";
  return `<br/><small>${site}${suffix}</small>` +
    `<br/><small>  Ellipse: ${_v(ellipseStatus)} · Tracker: ${_v(trackerStatus)}</small>`;
}

function _projectHtml(p) {
  if (!p.project_id) return "";
  const status = p.project_status ? ` · ${p.project_status}` : "";
  return `<br/>Project: ${p.project_id}${status}`;
}

function _openSitePopup(layer, p, callbacks) {
  const div = L.DomUtil.create("div", "net-popup");
  div.innerHTML =
    `<strong>${p.name}</strong>${p.name2 ? `<br/><em>${p.name2}</em>` : ""}` +
    `<br/>${p.site_type || "—"} · ${p.site_status || "—"}` +
    (p.s_number ? `<br/><small>${p.s_number}</small>` : "") +
    (p.flags ? `<br/><small class="net-flags">${p.flags.replaceAll(";", " · ")}</small>` : "") +
    `<div class="net-popup-actions">
      <button data-a="siteA">→ Site A</button>
      <button data-a="siteB">→ Site B</button>
    </div>`;
  _on(div, "siteA", () => { callbacks.onSiteA(p); layer.closePopup(); });
  _on(div, "siteB", () => { callbacks.onSiteB(p); layer.closePopup(); });
  layer.bindPopup(div, { maxWidth: 300 }).openPopup();
}

function _openLinkPopup(layer, p, callbacks, latlng) {
  const div = L.DomUtil.create("div", "net-popup");
  div.innerHTML =
    `<strong>${p.name}</strong>` +
    `<br/>State: ${_v(p.state)} · Status: ${_v(p.status)}` +
    `<br/>License: ${_v(p.license_status)}` +
    `<br/>Radio: ${_v(p.radio_type)}${p.channel ? ` · ${p.channel}` : ""}` +
    _opt("BNetzA", p.bnetza_link_id) +
    _opt("Customer", p.customer) +
    _projectHtml(p) +
    _opt("Ellipse RC Planer", p.rc_planer) +
    _opt("Ellipse DR Planer", p.dr_planer) +
    _sideHtml(p.site_a, p.s_number_a, p.site_status_a, p.tracker_status_a) +
    _sideHtml(p.site_b, p.s_number_b, p.site_status_b, p.tracker_status_b) +
    `<div class="net-popup-actions"><button data-a="corridor">→ Corridor</button></div>`;
  _on(div, "corridor", () => { callbacks.onCorridor(p); layer.closePopup(); });
  _appendProfileAction(div, () => { callbacks.onProfile?.(p, latlng); layer.closePopup(); });
  layer.bindPopup(div, { maxWidth: 340 }).openPopup();
}

function _on(container, action, handler) {
  container.querySelector(`[data-a="${action}"]`)?.addEventListener("click", handler);
}

function _appendProfileAction(container, handler) {
  const actions = container.querySelector(".net-popup-actions");
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Profile";
  button.addEventListener("click", handler);
  actions?.appendChild(button);
}
