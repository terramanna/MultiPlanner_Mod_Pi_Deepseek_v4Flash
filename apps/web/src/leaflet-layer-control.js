import {
  streets,
  satellite,
  nrwDop,
  byDop,
  thDop,
  bbDop,
  hhDop,
  hbDop,
  niDop,
  beDop,
  snDop,
  mvDop,
  heDop,
  heDgm,
  heDom,
  shDop,
  stDop,
  bwDop,
  rpDop,
  slDop,
  slDom,
  nrwTopo,
  byTopo,
  nrwHillshade,
  nrwNdom,
  bbInspireDom,
  globalHillshade,
} from "./leaflet-basemaps.js";

export function addLeafletLayerControl(L, map, bbLod2Layer) {
  streets.addTo(map);
  L.control.layers(baseLayers(), overlays(bbLod2Layer), { position: "topright" }).addTo(map);
}

function baseLayers() {
  return {
    Streets: streets,
    Satellite: satellite,
    "Baden-Württemberg Ortho (DOP20)": bwDop,
    "Bayern Ortho (DOP20)": byDop,
    "Berlin Ortho (DOP20)": beDop,
    "Brandenburg Ortho (DOP20c)": bbDop,
    "Bremen Ortho (DOP20)": hbDop,
    "Hamburg Ortho (DOP)": hhDop,
    "Hessen Ortho (DOP20)": heDop,
    "Mecklenburg-Vorpommern Ortho (DOP20)": mvDop,
    "Niedersachsen Ortho (DOP20)": niDop,
    "NRW Ortho (DOP)": nrwDop,
    "Rheinland-Pfalz Ortho (DOP20)": rpDop,
    "Saarland Ortho (DOP20)": slDop,
    "Sachsen Ortho (DOP20)": snDop,
    "Sachsen-Anhalt Ortho (DOP20)": stDop,
    "Schleswig-Holstein Ortho (DOP20)": shDop,
    "Thüringen Ortho (DOP)": thDop,
    "NRW Topo (DTK)": nrwTopo,
    "Bayern Topo (DTK25)": byTopo,
  };
}

function overlays(bbLod2Layer) {
  return {
    "Hillshade (global, ESRI)": globalHillshade,
    "NRW Hillshade (1m DGM)": nrwHillshade,
    "NRW nDOM50 (relative height)": nrwNdom,
    "BB DOM (absolute elevation)": bbInspireDom,
    "BB LoD2 Buildings (height ≥14)": bbLod2Layer,
    "Hessen DGM1 (AdV-Farbe)": heDgm,
    "Hessen DOM1 (AdV-Farbe)": heDom,
    "Saarland DOM1 shaded [eval]": slDom,
  };
}
