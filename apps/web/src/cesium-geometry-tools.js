import {
  bboxGeometry,
  circlePolygon,
  corridorGeometry,
  polygonGeometry,
} from "./cesium-geometry.js";

export function createGeometryTools(context) {
  const handler = new context.Cesium.ScreenSpaceEventHandler(context.viewer.scene.canvas);
  handler.setInputAction((movement) => handleClick(context, movement.position), context.Cesium.ScreenSpaceEventType.LEFT_CLICK);
  handler.setInputAction(() => finishPolygon(context), context.Cesium.ScreenSpaceEventType.RIGHT_CLICK);
  return {
    clear: () => clearGeometry(context),
    currentGeometry: () => currentGeometry(context.state),
    destroy: () => handler.destroy(),
    setMode: (mode) => setMode(context, mode),
  };
}

function handleClick(context, position) {
  if (context.beforeSample?.(position)) return;
  const sample = pickSample(context, position);
  if (!sample) return;
  const mode = context.state.geometryMode;
  if (mode === "corridor") return updateCorridor(context, sample);
  if (mode === "point") return setPoint(context, sample);
  if (mode === "rectangle") return updateRectangle(context, sample);
  if (mode === "circle") return updateCircle(context, sample);
  updatePolygon(context, sample);
}

function setMode(context, mode) {
  context.state.geometryMode = mode;
  context.state.geometryDraft = null;
  clearManualEntity(context);
  context.state.manualGeometry = null;
  context.setStatus(modeMessage(mode));
  context.onGeometryChange(currentGeometry(context.state));
}

function updateCorridor(context, sample) {
  context.onCorridorSample(sample);
  context.onGeometryChange(currentGeometry(context.state));
}

function setPoint(context, sample) {
  context.state.point = sample;
  context.state.manualGeometry = { kind: "point", lon: sample.lon, lat: sample.lat };
  replaceEntity(context, pointEntity(context, sample));
  complete(context, "Point selection ready.");
}

function updateRectangle(context, sample) {
  const first = context.state.geometryDraft?.first;
  if (!first) return startDraft(context, { first: sample }, "Rectangle mode: click the opposite corner.");
  const geometry = bboxGeometry(first, sample);
  context.state.manualGeometry = geometry;
  replaceEntity(context, polygonEntity(context, rectangleCoordinates(geometry), false));
  complete(context, "Rectangle selection ready.");
}

function updateCircle(context, sample) {
  const first = context.state.geometryDraft?.first;
  if (!first) return startDraft(context, { first: sample }, "Circle mode: click the edge point.");
  const geometry = circlePolygon(first, sample);
  context.state.manualGeometry = geometry;
  replaceEntity(context, polygonEntity(context, geometry.coordinates, true));
  complete(context, "Circle selection ready.");
}

function updatePolygon(context, sample) {
  const vertices = [...(context.state.geometryDraft?.vertices || []), sample];
  context.state.geometryDraft = { vertices };
  replacePreview(context, previewEntity(context, vertices));
  context.setStatus(vertices.length < 3 ? "Polygon mode: add more vertices." : "Polygon mode: right-click to finish.");
}

function finishPolygon(context) {
  if (context.state.geometryMode !== "polygon") return;
  const geometry = polygonGeometry(context.state.geometryDraft?.vertices || []);
  if (!geometry) return context.setStatus("Polygon needs at least three points.");
  context.state.manualGeometry = geometry;
  removeEntity(context.state.previewEntity, context.viewer);
  context.state.previewEntity = null;
  replaceEntity(context, polygonEntity(context, geometry.coordinates, true));
  complete(context, "Polygon selection ready.");
}

function complete(context, message) {
  context.state.geometryDraft = null;
  context.setStatus(message);
  context.onGeometryChange(currentGeometry(context.state));
  context.viewer.scene.requestRender();
}

function startDraft(context, draft, message) {
  context.state.geometryDraft = draft;
  context.setStatus(message);
}

function currentGeometry(state) {
  if (state.geometryMode === "corridor") return corridorGeometry(state.siteA, state.siteB);
  return state.manualGeometry;
}

function clearGeometry(context) {
  clearManualEntity(context);
  removeEntity(context.state.previewEntity, context.viewer);
  context.state.previewEntity = null;
  context.state.manualGeometry = null;
  context.state.geometryDraft = null;
  context.state.point = null;
  context.onGeometryChange(currentGeometry(context.state));
}

function clearManualEntity(context) {
  removeEntity(context.state.manualEntity, context.viewer);
  context.state.manualEntity = null;
}

function replaceEntity(context, entity) {
  clearManualEntity(context);
  context.state.manualEntity = entity;
}

function replacePreview(context, entity) {
  removeEntity(context.state.previewEntity, context.viewer);
  context.state.previewEntity = entity;
}

function pointEntity(context, sample) {
  return context.viewer.entities.add({
    position: context.Cesium.Cartesian3.fromDegrees(sample.lon, sample.lat),
    point: { pixelSize: 11, color: context.Cesium.Color.YELLOW },
  });
}

function polygonEntity(context, coordinates, filled) {
  return context.viewer.entities.add({
    polygon: {
      hierarchy: context.Cesium.Cartesian3.fromDegreesArray(coordinates.flat()),
      material: context.Cesium.Color.YELLOW.withAlpha(filled ? 0.22 : 0.1),
      outline: true,
      outlineColor: context.Cesium.Color.YELLOW,
    },
  });
}

function previewEntity(context, vertices) {
  if (vertices.length === 1) return pointEntity(context, vertices[0]);
  return context.viewer.entities.add({
    polyline: {
      positions: context.Cesium.Cartesian3.fromDegreesArray(vertices.flatMap(({ lon, lat }) => [lon, lat])),
      width: 2,
      material: context.Cesium.Color.YELLOW,
    },
  });
}

function pickSample(context, position) {
  let cartesian = context.viewer.scene.pickPositionSupported
    ? context.viewer.scene.pickPosition(position)
    : null;
  if (!context.Cesium.defined(cartesian)) {
    cartesian = context.viewer.camera.pickEllipsoid(position, context.viewer.scene.globe.ellipsoid);
  }
  if (!context.Cesium.defined(cartesian)) return null;
  const value = context.Cesium.Cartographic.fromCartesian(cartesian);
  return {
    lon: context.Cesium.Math.toDegrees(value.longitude),
    lat: context.Cesium.Math.toDegrees(value.latitude),
    height: value.height || 0,
  };
}

function rectangleCoordinates(geometry) {
  return [
    [geometry.west, geometry.north], [geometry.east, geometry.north],
    [geometry.east, geometry.south], [geometry.west, geometry.south],
  ];
}

function modeMessage(mode) {
  if (mode === "corridor") return "Corridor mode: place Site A and Site B.";
  if (mode === "point") return "Point mode: click once.";
  if (mode === "rectangle") return "Rectangle mode: click two opposite corners.";
  if (mode === "circle") return "Circle mode: click center, then edge.";
  return "Polygon mode: click vertices, right-click to finish.";
}

function removeEntity(entity, viewer) {
  if (entity) viewer.entities.remove(entity);
}
