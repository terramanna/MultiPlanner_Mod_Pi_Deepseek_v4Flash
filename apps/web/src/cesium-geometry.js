export function corridorGeometry(siteA, siteB, bufferM = 75) {
  if (!(siteA && siteB)) return null;
  return {
    kind: "corridor",
    from_lon: siteA.lon,
    from_lat: siteA.lat,
    to_lon: siteB.lon,
    to_lat: siteB.lat,
    buffer_m: bufferM,
  };
}

export function bboxGeometry(first, second) {
  return {
    kind: "bbox",
    west: Math.min(first.lon, second.lon),
    south: Math.min(first.lat, second.lat),
    east: Math.max(first.lon, second.lon),
    north: Math.max(first.lat, second.lat),
  };
}

export function circlePolygon(center, edge, points = 32) {
  const radiusM = distanceMeters(center, edge);
  const earthRadiusM = 6371000;
  const latitude = center.lat * Math.PI / 180;
  const coordinates = Array.from({ length: points }, (_, index) => {
    const angle = index * 2 * Math.PI / points;
    const lat = center.lat + (radiusM * Math.cos(angle) / earthRadiusM) * 180 / Math.PI;
    const lon = center.lon + (radiusM * Math.sin(angle) / (earthRadiusM * Math.cos(latitude))) * 180 / Math.PI;
    return [lon, lat];
  });
  return { kind: "polygon", coordinates };
}

export function polygonGeometry(vertices) {
  if (vertices.length < 3) return null;
  return { kind: "polygon", coordinates: vertices.map(({ lon, lat }) => [lon, lat]) };
}

export function distanceMeters(first, second) {
  const radiusM = 6371000;
  const deltaLat = ((second.lat - first.lat) * Math.PI) / 180;
  const deltaLon = ((second.lon - first.lon) * Math.PI) / 180;
  const firstLat = (first.lat * Math.PI) / 180;
  const secondLat = (second.lat * Math.PI) / 180;
  const haversine = Math.sin(deltaLat / 2) ** 2
    + Math.cos(firstLat) * Math.cos(secondLat) * Math.sin(deltaLon / 2) ** 2;
  return 2 * radiusM * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
}
