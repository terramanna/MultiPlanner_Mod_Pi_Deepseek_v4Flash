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
  const response = await fetch(`${apiBaseUrl}/api/v1/probe/point`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, dataset: "dom1", lat, lon }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? response.statusText);
  }
  return response.json();
}

function _formatResult(r) {
  return (
    `<b>${r.dataset.toUpperCase()}</b> · ${r.provider}<br/>` +
    `${r.lat.toFixed(6)}, ${r.lon.toFixed(6)}<br/>` +
    `<b style="font-size:1.15em">${r.height_m.toFixed(2)} m</b>`
  );
}
