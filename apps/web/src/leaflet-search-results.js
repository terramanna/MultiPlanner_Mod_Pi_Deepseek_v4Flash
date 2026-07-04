export function searchPlacementTarget(state) {
  if (state.activeSite === "A" || state.activeSite === "B") return state.activeSite;
  if (!state.siteA) return "A";
  if (!state.siteB) return "B";
  return "A";
}

export function applySearchCandidateToState(context) {
  const { candidate, state, variant, redrawGeometry, refreshReadout } = context;
  if (variant !== "corridor") return { applied: false };
  if (isNetworkLink(candidate)) {
    state.siteA = siteFromCandidate(candidate, "a");
    state.siteB = siteFromCandidate(candidate, "b");
    state.selectedNetworkLink = candidate;
    redrawGeometry();
    refreshReadout();
    return { applied: true, bounds: [state.siteA, state.siteB], status: "Placed network link." };
  }
  const target = searchPlacementTarget(state);
  state.activeSite = target;
  state.selectedNetworkLink = null;
  state[target === "A" ? "siteA" : "siteB"] = { lat: candidate.lat, lon: candidate.lon };
  redrawGeometry();
  refreshReadout();
  return { applied: true, panTo: { lat: candidate.lat, lon: candidate.lon }, status: `Placed Site ${target}.` };
}

function isNetworkLink(candidate) {
  return candidate.source === "network-link"
    && Number.isFinite(candidate.site_a_lat)
    && Number.isFinite(candidate.site_a_lon)
    && Number.isFinite(candidate.site_b_lat)
    && Number.isFinite(candidate.site_b_lon);
}

function siteFromCandidate(candidate, side) {
  return {
    lat: candidate[`site_${side}_lat`],
    lon: candidate[`site_${side}_lon`],
    name: candidate[`site_${side}_name`] || "",
    label: candidate[`site_${side}_label`] || "",
    id: candidate[`site_${side}_id`] || "",
    type: candidate[`site_${side}_type`] || "",
    structure: candidate[`site_${side}_structure`] || "",
  };
}
