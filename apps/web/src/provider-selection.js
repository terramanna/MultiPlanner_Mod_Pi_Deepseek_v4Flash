export function selectedProviderFromSelect(providerSelect, providers, fallbackProvider) {
  if (providers.some((provider) => provider.name === providerSelect.value)) {
    return providerSelect.value;
  }
  if (providers.some((provider) => provider.name === fallbackProvider)) {
    return fallbackProvider;
  }
  return providers[0]?.name || "";
}

export function providerDatasets(providers, providerName) {
  return providers.find((provider) => provider.name === providerName)?.datasets || [];
}

export function coverageShouldShow(selectedProvider, coverageProvider, coverageEnabled) {
  return coverageEnabled && (selectedProvider === "auto" || coverageProvider === selectedProvider);
}

export function applyProviderSelection(options) {
  const selected = selectedProviderFromSelect(options.providerSelect, options.providers, options.state.provider);
  options.state.provider = selected;
  options.providerSelect.value = selected;
  options.renderDatasetChoices(providerDatasets(options.providers, selected));
  options.updateCoverageOverlay();
  options.clearTiles?.();
  return selected;
}
