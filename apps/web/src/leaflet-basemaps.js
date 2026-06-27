import L from "leaflet";

export const streets = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "OpenStreetMap contributors"
});
export const satellite = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  { maxZoom: 19, attribution: "Tiles Esri" }
);
export const nrwDop = L.tileLayer.wms("https://www.wms.nrw.de/geobasis/wms_nw_dop", {
  layers: "nw_dop_rgb",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 19,
  attribution: "© Geobasis NRW"
});
export const byDop = L.tileLayer.wms("https://geoservices.bayern.de/od/wms/dop/v1/dop20", {
  layers: "by_dop20c",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 19,
  attribution: "© Bayerische Vermessungsverwaltung"
});
export const byTopo = L.tileLayer.wms("https://geoservices.bayern.de/od/wms/dtk/v1/dtk25", {
  layers: "by_dtk25",
  format: "image/png",
  transparent: false,
  maxZoom: 19,
  attribution: "© Bayerische Vermessungsverwaltung"
});
export const thDop = L.tileLayer.wms("https://www.geoproxy.geoportal-th.de/geoproxy/services/DOP", {
  layers: "th_dop",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 21,
  attribution: "© TLBG Thüringen"
});
export const bbDop = L.tileLayer.wms("https://isk.geobasis-bb.de/mapproxy/dop20c/service/wms", {
  layers: "bebb_dop20c",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 21,
  attribution: "© GeoBasis-DE/LGB"
});
export const hhDop = L.tileLayer.wms("https://geodienste.hamburg.de/HH_WMS_DOP_belaubt", {
  layers: "DOP_belaubt",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 20,
  attribution: "© LGV Hamburg"
});
export const nrwTopo = L.tileLayer.wms("https://www.wms.nrw.de/geobasis/wms_nw_dtk", {
  layers: "nw_dtk_col",
  format: "image/png",
  transparent: false,
  maxZoom: 19,
  attribution: "© Geobasis NRW"
});
export const nrwHillshade = L.tileLayer.wms("https://www.wms.nrw.de/geobasis/wms_nw_dgm-schummerung", {
  layers: "nw_dgm-schummerung_col",
  format: "image/png",
  transparent: true,
  opacity: 0.6,
  maxZoom: 19,
  attribution: "© Geobasis NRW"
});
export const hbDop = L.tileLayer.wms("https://geodienste.bremen.de/wms_dop20_2023", {
  layers: "DOP20_2023_HB,DOP20_2023_BHV",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 20,
  attribution: "© Landesamt GeoInformation Bremen"
});
export const niDop = L.tileLayer.wms("https://opendata.lgln.niedersachsen.de/doorman/noauth/dop_wms", {
  layers: "ni_dop20",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 20,
  attribution: "© LGLN Niedersachsen"
});
export const beDop = L.tileLayer.wms("https://gdi.berlin.de/services/wms/truedop_2024", {
  layers: "truedop_2024",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 20,
  attribution: "© SenStadt Berlin"
});
export const snDop = L.tileLayer.wms("https://geodienste.sachsen.de/wms_geosn_dop-rgb/guest", {
  layers: "sn_dop_020",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 20,
  attribution: "© GeoSN Sachsen"
});
export const mvDop = L.tileLayer.wms("https://www.geodaten-mv.de/dienste/adv_dop20", {
  layers: "mv_dop",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 20,
  attribution: "© LAiV Mecklenburg-Vorpommern"
});
export const heDop = L.tileLayer.wms("https://www.gds-srv.hessen.de/cgi-bin/lika-services/ogc-free-images.ows", {
  layers: "he_dop20_rgb",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 20,
  attribution: "© HVBG Hessen"
});
export const shDop = L.tileLayer.wms("https://service.gdi-sh.de/WMS_SH_DOP20col_OpenGBD", {
  layers: "sh_dop20_rgb",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 20,
  attribution: "© GeoBasis-DE/LVermGeo SH/CC BY-SA 4.0"
});
export const stDop = L.tileLayer.wms("https://www.geodatenportal.sachsen-anhalt.de/wss/service/ST_LVermGeo_GDI_DOP20/guest", {
  layers: "lsa_lvermgeo_dop20",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 20,
  attribution: "© LVermGeo Sachsen-Anhalt"
});
export const bwDop = L.tileLayer.wms("https://owsproxy.lgl-bw.de/owsproxy/ows/WMS_LGL-BW_ATKIS_DOP_20_C", {
  layers: "IMAGES_DOP_20_RGB",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 20,
  attribution: "© LGL Baden-Württemberg"
});
export const rpDop = L.tileLayer.wms("https://geo4.service24.rlp.de/wms/rp_dop20.fcgi", {
  layers: "rp_dop20",
  format: "image/jpeg",
  transparent: false,
  maxZoom: 20,
  attribution: "© Vermessungs- und Katasterverwaltung RLP"
});
