const renderer = new URLSearchParams(window.location.search).get("renderer");

if (renderer === "cesium") {
  await import("./main.js");
} else {
  await import("./leaflet-prototype.js");
}
