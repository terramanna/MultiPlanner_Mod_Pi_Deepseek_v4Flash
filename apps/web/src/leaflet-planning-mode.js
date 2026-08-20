export const PLANNING_MODE_LABELS = Object.freeze({
  corridor: "A - Two sites / corridor",
  area: "B - Draw rectangular area",
  point: "C - Single point",
});

export function changePlanningMode(options) {
  if (!Object.hasOwn(PLANNING_MODE_LABELS, options.next)) return false;
  options.setVariant(options.next);
  options.heading.textContent = PLANNING_MODE_LABELS[options.next];
  options.select.value = options.next;
  options.measurement.hidden = options.next !== "area";
  options.configure();
  options.updateDrawingControls(options.next);
  options.history.replaceState(null, "", planningModeSearch(options.search, options.next));
  return true;
}

export function planningModeSearch(search, variant) {
  const params = new URLSearchParams(search);
  params.set("variant", variant);
  return `?${params.toString()}`;
}
