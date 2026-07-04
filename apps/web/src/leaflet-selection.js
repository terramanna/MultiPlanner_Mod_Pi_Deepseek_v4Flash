export function clearLeafletSelection(context) {
  const { state, map, redrawGeometry, refreshReadout, downloadStatus, tileList } = context;
  state.siteA = null;
  state.siteB = null;
  state.selectedNetworkLink = null;
  state.point = null;
  state.areaStart = null;
  if (state.rectangle) map.removeLayer(state.rectangle);
  state.rectangle = null;
  if (state.manualLayer) map.removeLayer(state.manualLayer);
  state.manualLayer = null;
  state.manualGeometry = null;
  redrawGeometry();
  refreshReadout();
  downloadStatus.textContent = "Selection cleared.";
  tileList.innerHTML = "";
}
