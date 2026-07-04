export function mapStyle(apiBaseUrl) {
  return {
    version: 8,
    sources: rasterSources(apiBaseUrl),
    layers: rasterLayers(),
  };
}

function rasterSources(apiBaseUrl) {
  return {
    osm: rasterSource("https://tile.openstreetmap.org/{z}/{x}/{y}.png", "OpenStreetMap contributors"),
    "nrw-dop": wmsSource("https://www.wms.nrw.de/geobasis/wms_nw_dop", "nw_dop_rgb", "image/jpeg"),
    "nrw-topo": wmsSource("https://www.wms.nrw.de/geobasis/wms_nw_dtk", "nw_dtk_col", "image/png"),
    "nrw-dtm": wmsSource("https://www.wms.nrw.de/geobasis/wms_nw_dgm-schummerung", "nw_dgm-schummerung_col", "image/png"),
    "nrw-dhm-overview": wmsSource("https://www.wms.nrw.de/geobasis/wms_nw_dhm-uebersicht", "nw_dhm-uebersicht_planung_2024-2028", "image/png"),
    "nrw-ndom50-wms": wmsSource("https://www.wms.nrw.de/geobasis/wms_nw_ndom", "nw_ndom", "image/png"),
    "nrw-dgm1-local": localSource(apiBaseUrl, "dgm1"),
    "nrw-dom1-local": localSource(apiBaseUrl, "dom1"),
    "nrw-dom1-hillshade-local": localSource(apiBaseUrl, "dom1hs"),
    "nrw-ndsm-local": localSource(apiBaseUrl, "ndsm"),
  };
}

function wmsSource(baseUrl, layers, format) {
  return rasterSource(wmsUrl(baseUrl, layers, format), "Geobasis NRW");
}

function localSource(apiBaseUrl, dataset) {
  return rasterSource(`${apiBaseUrl}/api/v1/tiles/geobasis-nrw/${dataset}/{z}/{x}/{y}.png`, "Geobasis NRW, local cache");
}

function rasterSource(url, attribution) {
  return { type: "raster", tiles: [url], tileSize: 256, attribution };
}

function rasterLayers() {
  return [
    { id: "osm", type: "raster", source: "osm" },
    hiddenRasterLayer("nrw-dop"),
    hiddenRasterLayer("nrw-topo"),
    hiddenRasterLayer("nrw-dtm"),
    hiddenRasterLayer("nrw-dhm-overview"),
    hiddenRasterLayer("nrw-ndom50-wms"),
    hiddenRasterLayer("nrw-dgm1-local"),
    hiddenRasterLayer("nrw-dom1-local"),
    hiddenRasterLayer("nrw-dom1-hillshade-local", { visibility: "none" }, { "raster-opacity": 0.35 }),
    hiddenRasterLayer("nrw-ndsm-local"),
  ];
}

function hiddenRasterLayer(id, layout = { visibility: "none" }, paint = {}) {
  return {
    id,
    type: "raster",
    source: id,
    layout,
    paint,
  };
}

function wmsUrl(baseUrl, layers, format) {
  return `${baseUrl}?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=${layers}&STYLES=&CRS=EPSG:3857&BBOX={bbox-epsg-3857}&WIDTH=256&HEIGHT=256&FORMAT=${encodeURIComponent(format)}&TRANSPARENT=true`;
}
