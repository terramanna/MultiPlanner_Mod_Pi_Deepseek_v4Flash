export function bindPersistedInput(input, storageKey, storage = globalThis.localStorage) {
  try {
    const saved = storage.getItem(storageKey);
    if (saved !== null) {
      input.value = saved;
    }
  } catch (_error) {
    return;
  }
  input.addEventListener("input", () => {
    try {
      storage.setItem(storageKey, input.value);
    } catch (_error) {
      // Persistence is best-effort; typing must keep working.
    }
  });
}
