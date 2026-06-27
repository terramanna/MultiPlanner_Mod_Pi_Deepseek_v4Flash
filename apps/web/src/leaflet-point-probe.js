import L from "leaflet";

// Probe mode: toggle with the Probe DOM button; clicking the map reads DOM
// height at that point via the API instead of placing a site marker.
export function createPointProbe(map, apiBaseUrl, getProvider) {
  let active = false;
  let popup = null;

  function toggle() {
    active = !active;
    map.getContainer().classList.toggle("is-probe-active", active);
    if (!active) {
      popup?.remove();
      popup = null;
    }
    return active;
  }

  async function probe(latlng) {
    popup?.remove();
    popup = L.popup({ closeButton: true })
      .setLatLng(latlng)
      .setContent("Probing…")
      .addTo(map);
    try {
      const result = await _fetchProbe(apiBaseUrl, getProvider(), latlng.lat, latlng.lng);
      popup.setContent(_formatResult(result));
    } catch (err) {
      popup.setContent(`<em>${err.message}</em>`);
    }
  }

  function isActive() {
    return active;
  }

  return { toggle, probe, isActive };
}

async function _fetchProbe(apiBaseUrl, provider, lat, lon) {
  const response = await fetch(`${apiBaseUrl}/api/v1/probe/multi`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, lat, lon }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? response.statusText);
  }
  return response.json();
}

function _formatResult(r) {
  const fmt = (v) => (v != null ? `${v.toFixed(2)} m` : "—");
  const row = (label, v, err) =>
    `<tr><td><b>${label}</b></td><td style="padding-left:10px">${err ? `<em style="color:#c00">${err}</em>` : fmt(v)}</td></tr>`;
  return (
    `${r.provider}<br/>${r.lat.toFixed(6)}, ${r.lon.toFixed(6)}<br/>` +
    `<table style="margin-top:4px">` +
    row("DGM", r.dgm_m, r.dgm_error) +
    row("DOM", r.dom_m, r.dom_error) +
    row("nDSM", r.ndsm_m, null) +
    `</table>`
  );
}
