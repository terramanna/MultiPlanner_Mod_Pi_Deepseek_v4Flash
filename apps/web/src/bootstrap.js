const renderer = new URLSearchParams(window.location.search).get("renderer");

if (renderer === "maplibre") {
  await import("./maplibre-prototype.js");
} else if (renderer === "cesium") {
  await import("./main.js");
} else {
  await import("./leaflet-prototype.js");
}
