export function planningSelectionMarkers(state) {
  return [
    state.siteA && { sample: state.siteA, color: "#00c7ff", label: "A" },
    state.siteB && { sample: state.siteB, color: "#ff9f43", label: "B" },
    state.point && { sample: state.point, color: "#ffdd57", label: "P" },
  ].filter(Boolean);
}

export function planningSelectionReadout(state, variant, sampleText) {
  const lines = selectionLines(state, variant, sampleText);
  return lines.length ? lines.join("\n") : emptySelectionText(variant, sampleText(state.point));
}

function selectionLines(state, variant, sampleText) {
  return [
    activeSiteLine(state, variant),
    state.manualGeometry && `Manual ${state.manualGeometry.kind} selection`,
    state.selectedNetworkLink && `Link: ${networkLinkName(state.selectedNetworkLink)}`,
    ...siteLines(state, sampleText),
    state.rectangle && `Area: ${state.rectangle.getBounds().toBBoxString()}\nW, S, E, N`,
    state.point && `Point: ${sampleText(state.point)}`,
  ].filter(Boolean);
}

function activeSiteLine(state, variant) {
  if (variant !== "corridor" && !state.activeSite) return null;
  return `Active: ${state.activeSite ? `Site ${state.activeSite}` : "none"}`;
}

function siteLines(state, sampleText) {
  if (!state.siteA && !state.siteB) return [];
  return [`A: ${sampleText(state.siteA)}`, `B: ${sampleText(state.siteB)}`];
}

function networkLinkName(link) {
  return link.name || link.link_name || link.label || "selected";
}

function emptySelectionText(variant, pointText) {
  if (variant === "corridor") return "A: not set\nB: not set";
  if (variant === "area") return "Click two rectangle corners.";
  return pointText;
}
