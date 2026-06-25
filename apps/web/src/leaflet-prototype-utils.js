export function pointInRing(x, y, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export function pointInGeoJSONFeature(lat, lng, feature) {
  const geom = feature.geometry;
  const ringSets = geom.type === "MultiPolygon" ? geom.coordinates : [geom.coordinates];
  return ringSets.some((rings) => {
    if (!pointInRing(lng, lat, rings[0])) return false;
    for (let i = 1; i < rings.length; i++) {
      if (pointInRing(lng, lat, rings[i])) return false;
    }
    return true;
  });
}

export function geometryRepresentativePoints(geometry, state) {
  if (geometry.kind === "bbox") {
    return [
      [(geometry.north + geometry.south) / 2, (geometry.east + geometry.west) / 2],
      [geometry.north, geometry.west],
      [geometry.north, geometry.east],
      [geometry.south, geometry.west],
      [geometry.south, geometry.east],
    ];
  }
  if (geometry.kind === "polygon" && geometry.coordinates) {
    const coords = geometry.coordinates;
    const step = Math.max(1, Math.floor(coords.length / 8));
    const points = [];
    for (let i = 0; i < coords.length; i += step) points.push([coords[i][1], coords[i][0]]);
    const sumLat = coords.reduce((s, c) => s + c[1], 0) / coords.length;
    const sumLng = coords.reduce((s, c) => s + c[0], 0) / coords.length;
    points.push([sumLat, sumLng]);
    return points;
  }
  if (geometry.kind === "point") return [[geometry.lat, geometry.lon]];
  if (geometry.kind === "corridor" && state.siteA && state.siteB) {
    return [
      [state.siteA.lat, state.siteA.lon],
      [state.siteB.lat, state.siteB.lon],
      [(state.siteA.lat + state.siteB.lat) / 2, (state.siteA.lon + state.siteB.lon) / 2],
    ];
  }
  return [];
}

export function detectProviderTokens(geometry, state, providerCoverage) {
  const features = state.coverageFeatures;
  if (!Object.keys(features).length) return [];
  const found = new Set();
  for (const [lat, lng] of geometryRepresentativePoints(geometry, state)) {
    for (const [provider, feature] of Object.entries(features)) {
      if (pointInGeoJSONFeature(lat, lng, feature)) found.add(providerCoverage[provider].stateCode);
    }
  }
  return [...found].sort();
}

export function buildSelectionName(geometry, state, map, jobNameInput, providerCoverage) {
  const typedName = jobNameInput.value.trim();
  if (typedName) return slugName(typedName);
  const tokens = detectProviderTokens(geometry, state, providerCoverage);
  const region = tokens.length ? `_${tokens.join("_")}` : "";
  if (geometry.kind === "corridor" && state.siteA && state.siteB) {
    const lengthKm = map.distance([state.siteA.lat, state.siteA.lon], [state.siteB.lat, state.siteB.lon]) / 1000;
    const totalWidthToken = formatDimensionToken((geometry.buffer_m || 150) * 2);
    return slugName(`siteA_siteB_link_${formatKmToken(lengthKm)}_${totalWidthToken}_corridor${region}_1m_merge`);
  }
  if (geometry.kind === "point") {
    return slugName(`point_${coordinateToken(geometry.lat, geometry.lon)}${region}_1m_merge`);
  }
  if (geometry.kind === "bbox") {
    const widthM = distanceMeters(map, geometry.north, geometry.west, geometry.north, geometry.east);
    const heightM = distanceMeters(map, geometry.north, geometry.west, geometry.south, geometry.west);
    return slugName(`rectangle_${formatDimensionToken(widthM)}_${formatDimensionToken(heightM)}${region}_1m_merge`);
  }
  if (geometry.kind === "polygon" && geometry.name_hint) {
    return slugName(`${geometry.name_hint}${region}_1m_merge`);
  }
  if (geometry.kind === "polygon") {
    return slugName(`polygon_${formatDimensionToken(estimatedPolygonDiameterM(map, geometry.coordinates))}${region}_diameter_1m_merge`);
  }
  return slugName(`${geometry.kind}${region}_1m_merge`);
}

export function apiGeometry(geometry) {
  const { name_hint: _nameHint, ...payload } = geometry;
  return payload;
}

export function slugName(value) {
  return value
    .trim()
    .replace(/[^A-Za-z0-9_-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/_+/g, "_") || "subset_1m_merge";
}

export function coordinateToken(lat, lon) {
  const ns = lat >= 0 ? "n" : "s";
  const ew = lon >= 0 ? "e" : "w";
  return `${ns}${Math.abs(lat).toFixed(4)}_${ew}${Math.abs(lon).toFixed(4)}`;
}

export function formatKmToken(valueKm) {
  return `${formatNumberToken(valueKm)}km`;
}

export function formatDimensionToken(valueM) {
  return valueM >= 1000 ? `${formatNumberToken(valueM / 1000)}km` : `${Math.max(1, Math.round(valueM))}m`;
}

export function formatNumberToken(value) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, "").replace(".", "p");
}

export function distanceMeters(map, latA, lonA, latB, lonB) {
  return map.distance([latA, lonA], [latB, lonB]);
}

export function estimatedPolygonDiameterM(map, coordinates) {
  if (!coordinates.length) return 0;
  let maxDistance = 0;
  for (let index = 0; index < coordinates.length; index += 1) {
    for (let nextIndex = index + 1; nextIndex < coordinates.length; nextIndex += 1) {
      const [lonA, latA] = coordinates[index];
      const [lonB, latB] = coordinates[nextIndex];
      maxDistance = Math.max(maxDistance, distanceMeters(map, latA, lonA, latB, lonB));
    }
  }
  return maxDistance;
}

export function estimateText(payload) {
  return `Estimated source download: ${formatBytes(payload.total_estimated_source_bytes || 0)}. Estimated Ellipse merge: ${formatBytes(payload.total_estimated_ellipse_bytes || 0)}.`;
}

export function largeDownloadWarning(payload) {
  const sourceBytes = payload.total_estimated_source_bytes || 0;
  const ellipseBytes = payload.total_estimated_ellipse_bytes || 0;
  const tileCount = payload.results.reduce((total, result) => total + result.match_count, 0);
  if (sourceBytes < 1_000_000_000 && ellipseBytes < 1_000_000_000 && tileCount < 200) return "";
  return `Large download/export estimate:\n\nSource download: ${formatBytes(sourceBytes)}\nEllipse merge: ${formatBytes(ellipseBytes)}\nTiles: ${tileCount}\n\nLarge merged Ellipse rasters can be slow or fail to load. Continue?`;
}

export function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value >= 10 || unitIndex === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unitIndex]}`;
}

export function polygonAreaM2(points) {
  const radius = 6371000;
  return Math.abs(points.reduce((sum, point, index) => {
    const next = points[(index + 1) % points.length];
    return sum + (next.lng - point.lng) * Math.PI / 180 * (2 + Math.sin(point.lat * Math.PI / 180) + Math.sin(next.lat * Math.PI / 180));
  }, 0) * radius ** 2 / 2);
}

export function formatMeters(value) {
  return value >= 1000 ? `${(value / 1000).toFixed(2)} km` : `${Math.round(value)} m`;
}

export function formatArea(value) {
  return value >= 1_000_000 ? `${(value / 1_000_000).toFixed(2)} km2` : `${Math.round(value).toLocaleString()} m2`;
}

export function flattenLatLngs(values) {
  return values.flatMap((value) => Array.isArray(value) ? flattenLatLngs(value) : [value]);
}

export function circleCoordinates(center, radiusM) {
  const earthRadiusM = 6371000;
  const latRadians = center.lat * Math.PI / 180;
  return Array.from({ length: 32 }, (_, index) => {
    const angle = index * 2 * Math.PI / 32;
    const lat = center.lat + (radiusM * Math.cos(angle) / earthRadiusM) * 180 / Math.PI;
    const lon = center.lng + (radiusM * Math.sin(angle) / (earthRadiusM * Math.cos(latRadians))) * 180 / Math.PI;
    return [lon, lat];
  });
}

export function geometryFromLayer(layer, L, formatDimensionTokenFn = formatDimensionToken, flattenLatLngsFn = flattenLatLngs, circleCoordinatesFn = circleCoordinates) {
  if (layer instanceof L.Rectangle) {
    const bounds = layer.getBounds();
    return { kind: "bbox", west: bounds.getWest(), south: bounds.getSouth(), east: bounds.getEast(), north: bounds.getNorth() };
  }
  if (layer instanceof L.Circle) {
    const radiusM = layer.getRadius();
    return { kind: "polygon", coordinates: circleCoordinatesFn(layer.getLatLng(), radiusM), name_hint: `circle_${formatDimensionTokenFn(radiusM * 2)}_diameter` };
  }
  if (layer instanceof L.Polygon) {
    return { kind: "polygon", coordinates: flattenLatLngsFn(layer.getLatLngs()).map((latlng) => [latlng.lng, latlng.lat]) };
  }
  return null;
}

// Pure seam for leaflet-prototype.js currentGeometry(): turns the placement
// state + active variant into the API geometry payload. Extracted here so the
// branching is unit-testable without the Leaflet/DOM module side effects.
export function resolveCorridorBuffer(rawValue) {
  return Math.max(50, Math.min(2000, Number(rawValue) || 150));
}

export function corridorGeometry(state, bufferRawValue) {
  if (state.siteA && state.siteB) {
    return {
      kind: "corridor",
      from_lon: state.siteA.lon,
      from_lat: state.siteA.lat,
      to_lon: state.siteB.lon,
      to_lat: state.siteB.lat,
      buffer_m: resolveCorridorBuffer(bufferRawValue),
    };
  }
  const site = state.siteA || state.siteB;
  return site ? { kind: "point", lon: site.lon, lat: site.lat } : null;
}

export function bboxFromBounds(bounds) {
  return { kind: "bbox", west: bounds.getWest(), south: bounds.getSouth(), east: bounds.getEast(), north: bounds.getNorth() };
}

export function currentGeometryFrom(state, variant, bufferRawValue) {
  if (state.manualGeometry) return state.manualGeometry;
  if (variant === "corridor") return corridorGeometry(state, bufferRawValue);
  if (variant === "area") return state.rectangle ? bboxFromBounds(state.rectangle.getBounds()) : null;
  return state.point ? { kind: "point", lon: state.point.lon, lat: state.point.lat } : null;
}

export function selectedDatasets(doc = globalThis.document) {
  return [...doc.querySelectorAll('input[name="dataset"]:checked')].map((input) => input.value);
}

export function renderDatasetChoices(datasets, doc = globalThis.document) {
  const labels = {
    dgm1: "DGM1 - 1 m terrain",
    dom1: "DOM1 - 1 m surface",
    dop20: "DOP20 - 20 cm orthophoto"
  };
  const fieldset = doc.getElementById("datasetChoices");
  fieldset.innerHTML = "<legend>Download datasets</legend>";
  for (const dataset of datasets) {
    const label = doc.createElement("label");
    const input = doc.createElement("input");
    input.type = "checkbox";
    input.name = "dataset";
    input.value = dataset;
    input.checked = true;
    label.append(input, ` ${labels[dataset] || dataset}`);
    fieldset.appendChild(label);
  }
}

export function renderTiles(tiles, doc = globalThis.document) {
  const tileList = doc.getElementById("tileList");
  if (!tiles.length) {
    tileList.textContent = "No provider tiles matched this selection.";
    return;
  }
  tileList.innerHTML = `<strong>Tiles (${tiles.length})</strong><ul>${tiles.map((tile) => `<li><code>${escapeHtml(tile.provider || "provider")}/${escapeHtml(tile.dataset)}/${escapeHtml(tile.tileId || "unnamed-tile")}</code><br /><small>${escapeHtml(tile.path || "")}</small></li>`).join("")}</ul>`;
}

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
