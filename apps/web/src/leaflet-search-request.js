export function buildSearchPlacesUrl(apiBaseUrl, query, kind = "all", bounds = null) {
  const url = new URL(`${apiBaseUrl}/api/v1/search/places`);
  url.searchParams.set("q", query);
  url.searchParams.set("kind", kind);
  if (!bounds) return url.toString();
  url.searchParams.set("west", bounds.getWest().toFixed(6));
  url.searchParams.set("south", bounds.getSouth().toFixed(6));
  url.searchParams.set("east", bounds.getEast().toFixed(6));
  url.searchParams.set("north", bounds.getNorth().toFixed(6));
  return url.toString();
}
