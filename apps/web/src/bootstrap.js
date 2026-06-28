const renderer = new URLSearchParams(window.location.search).get("renderer");

if (renderer === "cesium") {
  await import("./main.js");
} else if (renderer === "maplibre") {
  await import("./maplibre-prototype.js");
} else {
  await import("./leaflet-prototype.js");
}
