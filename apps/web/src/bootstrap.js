const renderer = new URLSearchParams(window.location.search).get("renderer");

if (renderer === "cesium") {
  await import("./main.js");
} else if (renderer === "maplibre") {
  await import("./maplibre-prototype.js");
} else if (renderer === "leaflet-nrw") {
  await import("./leaflet-nrw-probe.js");
} else {
  await import("./leaflet-prototype.js");
}
