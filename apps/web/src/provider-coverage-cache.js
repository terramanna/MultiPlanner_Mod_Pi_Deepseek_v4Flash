const CACHE_KEY = "multiplanner.providerCoverage.v1";

export function loadProviderCoverageCache(storage = globalThis.localStorage) {
  const payload = readStoragePayload(storage);
  if (!payload || payload.version !== 1 || !isFeatureMap(payload.featuresByProvider)) {
    return null;
  }
  return payload.featuresByProvider;
}

export function saveProviderCoverageCache(featuresByProvider, storage = globalThis.localStorage) {
  if (!storage || !isFeatureMap(featuresByProvider)) {
    return;
  }
  try {
    storage.setItem(
      CACHE_KEY,
      JSON.stringify({ version: 1, featuresByProvider })
    );
  } catch {
    // Ignore storage failures; the live fetch still works.
  }
}

function readStoragePayload(storage) {
  if (!storage) {
    return null;
  }
  try {
    const raw = storage.getItem(CACHE_KEY);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function isFeatureMap(value) {
  return value && typeof value === "object" && !Array.isArray(value);
}
