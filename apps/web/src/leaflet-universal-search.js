import { buildSearchPlacesUrl } from "./leaflet-search-request.js";

export function bindUniversalSearch(context) {
  const search = () => runUniversalSearch(context);
  context.button.addEventListener("click", search);
  context.typeSelect.addEventListener("change", () => {
    if (context.input.value.trim()) search();
  });
  context.input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    search();
  });
}

export async function runUniversalSearch(context) {
  const query = context.input.value.trim();
  if (!query) return;
  context.status.textContent = "Searching...";
  context.results.innerHTML = "";
  try {
    const url = buildSearchPlacesUrl(context.apiBaseUrl, query, context.typeSelect.value);
    const response = await context.fetchFn(url);
    if (!response.ok) throw new Error("Search failed");
    const payload = await response.json();
    showCandidates(context, (payload.candidates || []).slice(0, 10));
  } catch {
    context.status.textContent = "Search failed.";
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
