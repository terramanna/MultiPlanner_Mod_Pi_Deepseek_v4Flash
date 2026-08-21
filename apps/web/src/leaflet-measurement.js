export function safeMeasurementText(layer, formatter) {
  if (!layer) return "Drawing selection...";
  try {
    return formatter(layer);
  } catch (_error) {
    return "Drawing selection...";
  }
}
