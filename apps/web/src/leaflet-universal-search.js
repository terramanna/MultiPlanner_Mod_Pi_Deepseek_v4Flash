import { buildSearchPlacesUrl } from "./leaflet-search-request.js";

export function bindUniversalSearch(context) {
  const runner = createSearchRunner(context);
  context.button.addEventListener("click", runner.runNow);
  context.typeSelect.addEventListener("change", runner.reset);
  context.input.addEventListener("input", runner.schedule);
  context.input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    runner.runNow();
  });
}

function createSearchRunner(context) {
  const setTimer = context.setTimeoutFn || globalThis.setTimeout;
  const clearTimer = context.clearTimeoutFn || globalThis.clearTimeout;
  let timer = null;
  let controller = null;
  const cancel = () => {
    if (timer !== null) clearTimer(timer);
    controller?.abort();
    timer = null;
  };
  const runNow = () => {
    cancel();
    controller = new AbortController();
    return runUniversalSearch({ ...context, signal: controller.signal });
  };
  const reset = () => { cancel(); resetUniversalSearch(context); };
  const schedule = () => {
    cancel();
    if (context.input.value.trim().length < 2) return resetUniversalSearch(context);
    timer = setTimer(runNow, 250);
  };
  return { reset, runNow, schedule };
}

export function resetUniversalSearch(context) {
  context.results.innerHTML = "";
  context.status.textContent = "";
}

export async function runUniversalSearch(context) {
  const query = context.input.value.trim();
  if (!query) return;
  context.status.textContent = "Searching...";
  context.results.innerHTML = "";
  try {
    const url = buildSearchPlacesUrl(context.apiBaseUrl, query, context.typeSelect.value);
    const response = await context.fetchFn(url, { signal: context.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status} from search service`);
    const payload = await response.json();
    showCandidates(context, (payload.candidates || []).slice(0, 10));
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    const detail = error instanceof Error ? error.message : "Unknown browser error";
    context.status.textContent = `Search failed: ${detail}`;
  }
}

function showCandidates(context, candidates) {
  if (candidates.length === 1 && candidates[0].source === "coordinates") {
    context.onCandidate(candidates[0]);
    return;
  }
  for (const candidate of candidates) appendCandidate(context, candidate);
  context.status.textContent = candidates.length ? "Choose a result." : "No matches found.";
}

function appendCandidate(context, candidate) {
  const button = context.results.ownerDocument.createElement("button");
  button.className = "prototype-result";
  button.textContent = candidate.label;
  button.addEventListener("click", () => context.onCandidate(candidate));
  context.results.appendChild(button);
}
