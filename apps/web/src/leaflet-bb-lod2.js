/**
 * BB/BE INSPIRE LoD2 building layer — height-coded polygons fetched live from WFS.
 *
 * Heights come from bu-base:heightAboveGround (measured, above ground).
 * Footprint is reconstructed as the convex hull of all face coordinates.
 * Only active at zoom 14+ to avoid flooding the WFS with large-area requests.
 */
import L from "leaflet";

const WFS_URL = "https://inspire.brandenburg.de/services/bu-core3d_lod2_wfs";
const NS_GML = "http://www.opengis.net/gml/3.2";
const NS_BU_BASE = "http://inspire.ec.europa.eu/schemas/bu-base/4.0";
const NS_BU_CORE3D = "http://inspire.ec.europa.eu/schemas/bu-core3d/4.0";
const MIN_ZOOM = 14;
const MAX_COUNT = 500;
const DEBOUNCE_MS = 400;

function heightToStyle(h) {
  if (h < 3)  return { fillColor: "#a8d5a2", fillOpacity: 0.20, color: "#6aaa62", weight: 0.5 };
  if (h < 8)  return { fillColor: "#d4ed57", fillOpacity: 0.45, color: "#b0c830", weight: 0.5 };
  if (h < 15) return { fillColor: "#ffb300", fillOpacity: 0.55, color: "#e07b00", weight: 0.5 };
  if (h < 25) return { fillColor: "#ff5c00", fillOpacity: 0.65, color: "#cc3b00", weight: 0.5 };
  return              { fillColor: "#cc0000", fillOpacity: 0.75, color: "#900000", weight: 0.5 };
}

// Andrew's monotone-chain convex hull — returns [lon, lat] pairs in CCW order.
function convexHull(pts) {
  if (pts.length < 3) return pts;
  const sorted = [...pts].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (O, A, B) => (A[0] - O[0]) * (B[1] - O[1]) - (A[1] - O[1]) * (B[0] - O[0]);
  const lower = [], upper = [];
  for (const p of sorted) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop();
    lower.push(p);
  }
  for (let i = sorted.length - 1; i >= 0; i--) {
    const p = sorted[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop();
    upper.push(p);
  }
  upper.pop(); lower.pop();
  return lower.concat(upper);
}

function parseBuildings(xmlText) {
  const doc = new DOMParser().parseFromString(xmlText, "application/xml");
  const buildings = [];
  for (const bldg of doc.getElementsByTagNameNS(NS_BU_CORE3D, "Building")) {
    const heightEl = bldg.getElementsByTagNameNS(NS_BU_BASE, "value")[0];
    if (!heightEl) continue;
    const height = parseFloat(heightEl.textContent);
    if (!isFinite(height) || height < 0) continue;

    // Collect all coordinate pairs from all polygon faces → convex hull = footprint
    const allPts = [];
    for (const posList of bldg.getElementsByTagNameNS(NS_GML, "posList")) {
      const nums = posList.textContent.trim().split(/\s+/).map(Number);
      for (let i = 0; i + 1 < nums.length; i += 2) {
        allPts.push([nums[i], nums[i + 1]]); // [lon, lat]
      }
    }
    if (allPts.length < 3) continue;

    const hull = convexHull(allPts);
    // Leaflet wants [lat, lon]
    const latLngs = hull.map(([lon, lat]) => [lat, lon]);
    buildings.push({ height, latLngs });
  }
  return buildings;
}

async function fetchBuildings(bounds) {
  const b = bounds;
  // EPSG:4326 BBOX order for WFS 2.0: minLat,minLon,maxLat,maxLon
  const bbox = `${b.getSouth()},${b.getWest()},${b.getNorth()},${b.getEast()},EPSG:4326`;
  const url = `${WFS_URL}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature` +
    `&TYPENAMES=bu-core3d:Building&SRSNAME=EPSG:4326&BBOX=${bbox}&COUNT=${MAX_COUNT}`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`WFS ${resp.status}`);
  return parseBuildings(await resp.text());
}

/**
 * Creates a self-updating LoD2 building layer group.
 * @param {L.Map} map
 * @returns {{ layerGroup: L.LayerGroup, destroy: () => void }}
 */
export function createLod2Layer(map) {
  const layerGroup = L.layerGroup();
  let debounceTimer = null;
  let active = false;

  async function refresh() {
    if (!active || map.getZoom() < MIN_ZOOM) {
      layerGroup.clearLayers();
      return;
    }
    let buildings;
    try {
      buildings = await fetchBuildings(map.getBounds());
    } catch (e) {
      console.warn("LoD2 WFS fetch failed:", e);
      return;
    }
    layerGroup.clearLayers();
    for (const { height, latLngs } of buildings) {
      L.polygon(latLngs, {
        ...heightToStyle(height),
        interactive: true,
      })
        .bindTooltip(`${height.toFixed(1)} m`, { sticky: true, direction: "top" })
        .addTo(layerGroup);
    }
  }

  function scheduleRefresh() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(refresh, DEBOUNCE_MS);
  }

  function onAdd() {
    active = true;
    scheduleRefresh();
    map.on("moveend zoomend", scheduleRefresh);
  }

  function onRemove() {
    active = false;
    clearTimeout(debounceTimer);
    layerGroup.clearLayers();
    map.off("moveend zoomend", scheduleRefresh);
  }

  // Hook into Leaflet's add/remove events via the LayerGroup
  layerGroup.on("add", onAdd);
  layerGroup.on("remove", onRemove);

  return layerGroup;
}
