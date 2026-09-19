const renderer = new URLSearchParams(window.location.search).get("renderer");

if (renderer === "cesium") {
  await import("./main.js");
} else if (renderer === "leaflet" || renderer === "leaflet-nrw") {
  await import("./leaflet-prototype.js");
} else {
  await import("./main.js");
}
