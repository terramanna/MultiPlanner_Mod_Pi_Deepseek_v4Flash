export function addAreaDrawingControls(map, variant) {
  if (variant !== "area") return false;
  map.pm.addControls({
    position: "topleft",
    drawMarker: false,
    drawCircleMarker: false,
    drawText: false,
    drawPolyline: false,
    drawRectangle: true,
    drawPolygon: true,
    drawCircle: true,
    editMode: true,
    dragMode: false,
    cutMode: false,
    rotateMode: false,
    scaleMode: false,
    removalMode: true,
  });
  return true;
}

export function updateAreaDrawingControls(map, variant) {
  disableActiveDraw(map);
  map.pm.removeControls();
  return addAreaDrawingControls(map, variant);
}

function disableActiveDraw(map) {
  const activeShape = map.pm.Draw?.getActiveShape?.();
  if (activeShape) map.pm.disableDraw(activeShape);
}
