import L from "leaflet";

const HOVER_DELAY_MS = 400;

export function createPointProbe(map, apiBaseUrl, getProvider, getDataset = () => "multi") {
  let active = false;
  let popup = null;
  let hoverMode = false;
  let hoverTimer = null;
  let lastLatlng = null;

  map.on("mousemove", (e) => {
    if (!active || !hoverMode) return;
    lastLatlng = e.latlng;
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => probe(e.latlng), HOVER_DELAY_MS);
  });

  function toggle() {
    active = !active;
    map.getContainer().classList.toggle("is-probe-active", active);
    if (!active) {
      popup?.remove();
      popup = null;
      clearTimeout(hoverTimer);
    }
    return active;
  }

  function setHoverMode(enabled) {
    hoverMode = enabled;
    clearTimeout(hoverTimer);
  }

  function sampleNow() {
    if (active && lastLatlng) probe(lastLatlng);
  }

  async function probe(latlng) {
    lastLatlng = latlng;
    popup?.remove();
    popup = L.popup({ closeButton: true })
      .setLatLng(latlng)
      .setContent("Probing…")
      .addTo(map);
    try {
      const dataset = getDataset();
      const result = dataset === "multi"
        ? await _fetchMultiProbe(apiBaseUrl, getProvider(), latlng.lat, latlng.lng)
        : await _fetchSingleProbe(apiBaseUrl, getProvider(), dataset, latlng.lat, latlng.lng);
      popup.setContent(_formatResult(result, dataset));
    } catch (err) {
      popup.setContent(`<em>${err.message}</em>`);
    }
  }

  return { toggle, probe, isActive: () => active, setHoverMode, sampleNow };
}

async function _fetchMultiProbe(apiBaseUrl, provider, lat, lon) {
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

async function _fetchSingleProbe(apiBaseUrl, provider, dataset, lat, lon) {
  const response = await fetch(`${apiBaseUrl}/api/v1/probe/point`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, dataset, lat, lon }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? response.statusText);
  }
  return response.json();
}

function _formatResult(r, dataset) {
  const fmt = (v) => (v != null ? `${v.toFixed(2)} m` : "—");
  const row = (label, v, err) =>
    `<tr><td><b>${label}</b></td><td style="padding-left:10px">${err ? `<em style="color:#c00">${err}</em>` : fmt(v)}</td></tr>`;
  const head = `${r.provider}<br/>${r.lat.toFixed(6)}, ${r.lon.toFixed(6)}<br/>`;
  if (dataset === "multi") {
    return head +
      `<table style="margin-top:4px">` +
      row("DGM", r.dgm_m, r.dgm_error) +
      row("DOM", r.dom_m, r.dom_error) +
      row("nDOM", r.ndsm_m, null) +
      `</table>`;
  }
  const label = dataset === "dgm1" ? "DGM" : dataset === "dom1" ? "DOM" : "nDOM";
  return head + `<b>${label}</b>: ${fmt(r.height_m)}`;
}
