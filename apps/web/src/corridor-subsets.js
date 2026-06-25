const CORRIDOR_DATASETS = ["dgm1", "dom1", "dop20"];
const CORRIDOR_BUFFER_M = 75;

export function buildCorridorSubsetRequest(siteA, siteB, exportProfile = "ellipse_mapinfo_tab") {
  return {
    provider: "auto",
    datasets: CORRIDOR_DATASETS,
    selection_name: buildCorridorSelectionName(siteA, siteB),
    export_profile: exportProfile,
    geometry: {
      kind: "corridor",
      from_lon: siteA.lon,
      from_lat: siteA.lat,
      to_lon: siteB.lon,
      to_lat: siteB.lat,
      buffer_m: CORRIDOR_BUFFER_M
    }
  };
}

export function buildCorridorSelectionName(siteA, siteB) {
  return `siteA_siteB_link_${formatKmToken(distanceKm(siteA, siteB))}_${formatMetersToken(CORRIDOR_BUFFER_M * 2)}_corridor_1m_merge`;
}

export function formatCorridorPreviewStatus(payload) {
  const summary = payload.results
    .map((entry) => `${entry.provider || payload.provider}/${entry.dataset}: ${entry.match_count}`)
    .join(" | ");
  return `${summary || "no subset matches"} | ${estimateText(payload)}${formatWarnings(payload.warnings)}`;
}

export function formatCorridorDownloadStatus(saved, payload) {
  return `saved ${saved.sourceFileCount} files and ${saved.exportFileCount} ellipse exports to ${saved.rootName}\\${saved.selectionName}${formatWarnings(payload.warnings)}`;
}

export function shouldWarnAboutLargeDownload(payload) {
  const sourceBytes = payload.total_estimated_source_bytes || 0;
  const ellipseBytes = payload.total_estimated_ellipse_bytes || 0;
  const tileCount = payload.results.reduce((total, result) => total + result.match_count, 0);
  return sourceBytes >= 1_000_000_000 || ellipseBytes >= 1_000_000_000 || tileCount >= 200;
}

export function largeDownloadWarning(payload) {
  return `Large download/export estimate:

Source download: ${formatBytes(payload.total_estimated_source_bytes || 0)}
Ellipse merge: ${formatBytes(payload.total_estimated_ellipse_bytes || 0)}
Tiles: ${payload.results.reduce((total, result) => total + result.match_count, 0)}

Large merged Ellipse rasters can be slow or fail to load. Continue?`;
}

function formatWarnings(warnings) {
  return warnings?.length ? ` warnings: ${warnings.join("; ")}` : "";
}

function estimateText(payload) {
  return `est source ${formatBytes(payload.total_estimated_source_bytes || 0)}, Ellipse merge ${formatBytes(payload.total_estimated_ellipse_bytes || 0)}`;
}

function distanceKm(first, second) {
  const radiusKm = 6371;
  const deltaLat = ((second.lat - first.lat) * Math.PI) / 180;
  const deltaLon = ((second.lon - first.lon) * Math.PI) / 180;
  const firstLat = (first.lat * Math.PI) / 180;
  const secondLat = (second.lat * Math.PI) / 180;
  const haversine = Math.sin(deltaLat / 2) ** 2 + Math.cos(firstLat) * Math.cos(secondLat) * Math.sin(deltaLon / 2) ** 2;
  return 2 * radiusKm * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
}

function formatKmToken(valueKm) {
  return `${formatNumberToken(valueKm)}km`;
}

function formatMetersToken(valueM) {
  return valueM >= 1000 ? `${formatNumberToken(valueM / 1000)}km` : `${Math.max(1, Math.round(valueM))}m`;
}

function formatNumberToken(value) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, "").replace(".", "p");
}

function formatBytes(bytes) {
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
