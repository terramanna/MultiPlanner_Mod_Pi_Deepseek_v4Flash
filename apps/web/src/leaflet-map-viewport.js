export const DEFAULT_LEAFLET_VIEW = Object.freeze({ lat: 51.1657, lon: 10.4515, zoom: 6 });

export function leafletViewFromSearch(search) {
  const params = new URLSearchParams(search);
  const view = {
    lat: numberParameter(params, "mapLat"),
    lon: numberParameter(params, "mapLon"),
    zoom: numberParameter(params, "mapZoom"),
  };
  if (!isValidView(view)) return DEFAULT_LEAFLET_VIEW;
  return view;
}

export function searchWithPlanningModeViewport(search, variant, center, zoom) {
  const params = new URLSearchParams(search);
  params.set("variant", variant);
  params.set("mapLat", center.lat.toFixed(6));
  params.set("mapLon", center.lng.toFixed(6));
  params.set("mapZoom", String(zoom));
  return `?${params.toString()}`;
}

function numberParameter(params, name) {
  const value = params.get(name);
  return value === null ? Number.NaN : Number(value);
}

function isValidView(view) {
  return Number.isFinite(view.lat)
    && Number.isFinite(view.lon)
    && Number.isFinite(view.zoom)
    && view.lat >= -90 && view.lat <= 90
    && view.lon >= -180 && view.lon <= 180
    && view.zoom >= 0 && view.zoom <= 22;
}
