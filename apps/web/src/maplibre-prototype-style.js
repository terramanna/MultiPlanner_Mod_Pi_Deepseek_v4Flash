export function mapStyle(apiBaseUrl) {
  return {
    version: 8,
    sources: rasterSources(apiBaseUrl),
    layers: rasterLayers(),
  };
}

function rasterSources(apiBaseUrl) {
  return {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "OpenStreetMap contributors",
    },
    "nrw-dop": {
      type: "raster",
      tiles: [wmsUrl("https://www.wms.nrw.de/geobasis/wms_nw_dop", "nw_dop_rgb", "image/jpeg")],
      tileSize: 256,
      attribution: "Geobasis NRW",
    },
    "nrw-topo": {
      type: "raster",
      tiles: [wmsUrl("https://www.wms.nrw.de/geobasis/wms_nw_dtk", "nw_dtk_col", "image/png")],
      tileSize: 256,
      attribution: "Geobasis NRW",
    },
    "nrw-dtm": {
      type: "raster",
      tiles: [wmsUrl("https://www.wms.nrw.de/geobasis/wms_nw_dgm-schummerung", "nw_dgm-schummerung_col", "image/png")],
      tileSize: 256,
      attribution: "Geobasis NRW",
    },
    "nrw-dhm-overview": {
      type: "raster",
      tiles: [wmsUrl("https://www.wms.nrw.de/geobasis/wms_nw_dhm-uebersicht", "nw_dhm-uebersicht_planung_2024-2028", "image/png")],
      tileSize: 256,
      attribution: "Geobasis NRW",
    },
    "nrw-ndom50-wms": {
      type: "raster",
      tiles: [wmsUrl("https://www.wms.nrw.de/geobasis/wms_nw_ndom", "nw_ndom", "image/png")],
      tileSize: 256,
      attribution: "Geobasis NRW",
    },
    "nrw-dgm1-local": {
      type: "raster",
      tiles: [`${apiBaseUrl}/api/v1/tiles/geobasis-nrw/dgm1/{z}/{x}/{y}.png`],
      tileSize: 256,
      attribution: "Geobasis NRW, local cache",
    },
    "nrw-dom1-local": {
      type: "raster",
      tiles: [`${apiBaseUrl}/api/v1/tiles/geobasis-nrw/dom1/{z}/{x}/{y}.png`],
      tileSize: 256,
      attribution: "Geobasis NRW, local cache",
    },
    "nrw-dom1-hillshade-local": {
      type: "raster",
      tiles: [`${apiBaseUrl}/api/v1/tiles/geobasis-nrw/dom1hs/{z}/{x}/{y}.png`],
      tileSize: 256,
      attribution: "Geobasis NRW, local cache",
    },
    "nrw-ndsm-local": {
      type: "raster",
      tiles: [`${apiBaseUrl}/api/v1/tiles/geobasis-nrw/ndsm/{z}/{x}/{y}.png`],
      tileSize: 256,
      attribution: "Geobasis NRW, local cache",
    },
  };
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
