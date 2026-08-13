export function clearLeafletSelection(context) {
  const { state, map, redrawGeometry, refreshReadout, downloadStatus, tileList, releaseProvider } = context;
  state.activeSite = null;
  state.searchSelectionActive = false;
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
  releaseProvider?.();
  redrawGeometry();
  refreshReadout();
  downloadStatus.textContent = "Selection cleared.";
  tileList.innerHTML = "";
}
