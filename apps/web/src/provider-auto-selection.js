import { geometryRepresentativePoints, pointInGeoJSONFeature } from "./leaflet-prototype-utils.js";

export function autoProviderForGeometry(geometry, state, coverageFeatures, availableProviders) {
  if (!geometry || !Object.keys(coverageFeatures).length) return null;
  const matches = matchingProviders(geometry, state, coverageFeatures);
  if (matches.size !== 1) return "auto";
  const [provider] = matches;
  return availableProviders.includes(provider) ? provider : "auto";
}

function matchingProviders(geometry, state, coverageFeatures) {
  const matches = new Set();
  for (const [lat, lon] of geometryRepresentativePoints(geometry, state)) {
    for (const [provider, feature] of Object.entries(coverageFeatures)) {
      if (pointInGeoJSONFeature(lat, lon, feature)) matches.add(provider);
    }
  }
  return matches;
}
