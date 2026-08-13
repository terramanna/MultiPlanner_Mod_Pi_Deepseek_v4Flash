import { chooseDownloadDirectory, saveSubsetPayloadToDirectory } from "./download-save.js";
import {
  apiGeometry,
  buildSelectionName,
  estimateText,
  largeDownloadWarning,
  renderTiles,
  selectedDatasets,
  slugName,
} from "./leaflet-prototype-utils.js";

export async function requestLeafletSubset(context, download) {
  const geometry = context.currentGeometry();
  if (!geometry) return setStatus(context, "Complete the selection first.");
  const datasets = selectedDatasets(context.document);
  if (!datasets.length) return setStatus(context, "Choose at least one dataset.");

  const exportProfile = download ? context.selectedExportProfile() : null;
  const profileError = exportProfileError(exportProfile, context.state.provider);
  if (profileError) return setStatus(context, profileError);

  const body = buildSubsetRequestBody(context, download, geometry, datasets, exportProfile);
  setStatus(context, download ? "Checking selected 1 m tiles..." : "Resolving available 1 m tiles...");
  try {
    const rootDirectoryHandle = download ? await prepareSubsetDownload(context, body) : null;
    if (download && !rootDirectoryHandle) return;
    await submitSubsetRequest(context, download, body, rootDirectoryHandle);
  } catch (error) {
    setStatus(context, failureStatus(download, error));
  }
}

function setStatus(context, message) {
  const completed = message.match(/^Processing tile (\d+) of (\d+)/);
  if (completed) message = `Processed ${completed[1]} of ${completed[2]} source tiles.`;
  context.downloadStatus.textContent = message;
}

function failureStatus(download, error) {
  const prefix = download ? "Download/export failed" : "Subset lookup failed";
  return error?.message ? `${prefix}: ${error.message}` : `${prefix}.`;
}

function buildSubsetRequestBody(context, download, geometry, datasets, exportProfile) {
  const body = { provider: context.state.provider, datasets, geometry: apiGeometry(geometry) };
  if (download) {
    body.selection_name = buildSelectionName(geometry, context.state, context.map, context.jobNameInput, context.providerCoverage);
    body.export_profile = exportProfile;
    body.datasets = datasetsForExport(body.datasets, exportProfile, body.provider);
  }
  return body;
}

function exportProfileError(exportProfile, provider) {
  if (exportProfile !== "ellipse_semantic_grc" || provider === "ldbv-by") return "";
  return "Buildings + trees GRC currently requires the Bayern LDBV provider.";
}

export function datasetsForExport(datasets, exportProfile, provider) {
  if (exportProfile !== "ellipse_semantic_grc" || provider !== "ldbv-by") return datasets;
  const required = ["dgm1", "dom1", "bdom"];
  return [...datasets, ...required.filter((dataset) => !datasets.includes(dataset))];
}

async function prepareSubsetDownload(context, body) {
  const preview = await fetchSubsetPreview(context, body);
  setDownloadTiles(context, preview);
  const warning = largeDownloadWarning(preview);
  if (warning && !context.confirm(warning)) return setCancelled(context);
  setStatus(context, "Choose an output folder to start the download/export.");
  try {
    const directoryHandle = await chooseDownloadDirectory();
    useSelectedDirectoryName(context, body, directoryHandle);
    return directoryHandle;
  } catch (_error) {
    return setCancelled(context);
  }
}

function useSelectedDirectoryName(context, body, directoryHandle) {
  if (context.jobNameInput?.value.trim() || !directoryHandle.name) return;
  body.selection_name = slugName(directoryHandle.name);
}

function setCancelled(context) {
  setStatus(context, "Download cancelled.");
  return null;
}

async function fetchSubsetPreview(context, body) {
  const response = await postJson(context, "/api/v1/subsets/locate", body);
  if (!response.ok) throw new Error(await errorDetail(response, "Subset preview failed"));
  return response.json();
}

async function submitSubsetRequest(context, download, body, rootDirectoryHandle) {
  if (download) return streamSubsetDownload(context, body, rootDirectoryHandle);
  const response = await postJson(context, "/api/v1/subsets/locate", body);
  if (!response.ok) throw new Error(await errorDetail(response, "Subset request failed"));
  return handlePreviewSubset(context, await response.json());
}

async function streamSubsetDownload(context, body, rootDirectoryHandle) {
  const response = await postJson(context, "/api/v1/subsets/download-stream", body);
  if (!response.ok) throw new Error(await errorDetail(response, "Download failed"));
  setStatus(context, "Downloading source tiles and building export...");
  const payload = await readDownloadStream(response.body, context);
  if (!payload) throw new Error("Download stream ended without result.");
  if (hasMissingDownloads(payload)) {
    return handleMissingDownloads(context, body, payload, rootDirectoryHandle);
  }
  return handleDownloadSubset(context, body, payload, rootDirectoryHandle);
}

async function readDownloadStream(body, context) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let payload = null;
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) return payload;
    buffer += decoder.decode(chunk.value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop();
    payload = applyStreamParts(parts, context, payload);
  }
}

function applyStreamParts(parts, context, payload) {
  let nextPayload = payload;
  for (const part of parts) {
    if (!part.startsWith("data: ")) continue;
    nextPayload = applyStreamEvent(JSON.parse(part.slice(6)), context, nextPayload);
  }
  return nextPayload;
}

function applyStreamEvent(event, context, payload) {
  if (event.type === "progress") {
    markDownloadTileComplete(context, event);
    setDownloadProgress(context, event.current, event.total);
    setStatus(context, `Processing tile ${event.current} of ${event.total}…`);
    return payload;
  }
  if (event.type === "done") return event.result;
  if (event.type === "error") throw new Error(event.message);
  return payload;
}

function setDownloadTiles(context, preview) {
  context.state.downloadTiles = preview.results.flatMap((result) => result.tiles.map((tile) => ({
    provider: tile.provider || result.provider || preview.provider,
    dataset: result.dataset,
    tileId: tile.tile_id,
    path: tile.primary_url,
    downloaded: false,
  })));
  renderTiles(context.state.downloadTiles, context.document);
  setDownloadProgress(context, 0, context.state.downloadTiles.length);
}

function markDownloadTileComplete(context, event) {
  const tile = context.state.downloadTiles?.find((candidate) => (
    candidate.provider === event.provider
    && candidate.dataset === event.dataset
    && candidate.tileId === (event.tile_id || null)
  ));
  if (!tile) return;
  tile.downloaded = event.success !== false;
  tile.failed = event.success === false;
  renderTiles(context.state.downloadTiles, context.document);
}

function setDownloadProgress(context, current, total) {
  const progress = context.downloadProgress;
  if (!progress) return;
  progress.hidden = false;
  progress.max = Math.max(total, 1);
  progress.value = Math.min(current, progress.max);
}

async function handleMissingDownloads(context, body, payload, rootDirectoryHandle) {
  const message = missingDownloadPrompt(payload.failed_downloads);
  if (context.confirm(message)) {
    setStatus(context, "Retrying missing source files...");
    return streamSubsetDownload(context, body, rootDirectoryHandle);
  }
  setStatus(context, `Download stopped. ${missingDownloadSummary(payload.failed_downloads)}`);
  return null;
}

async function errorDetail(response, fallback) {
  try {
    const payload = await response.json();
    return payload.detail || fallback;
  } catch (_error) {
    return fallback;
  }
}

function postJson(context, endpoint, body) {
  return context.fetch.call(globalThis, `${context.apiBaseUrl}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function handleDownloadSubset(context, body, payload, rootDirectoryHandle) {
  setStatus(context, "Saving downloaded files to the selected folder...");
  const saved = await saveSubsetPayloadToDirectory(context.apiBaseUrl, payload, rootDirectoryHandle);
  context.state.lastDownloadedOutputDir = payload.output_dir || null;
  context.openDownloadFolderButton.hidden = !context.state.lastDownloadedOutputDir;
  const warningHint = payload.warnings?.length ? ` Warnings: ${payload.warnings.join("; ")}.` : "";
  const exportLabel = exportProfileLabel(body.export_profile);
  setStatus(context, `Saved ${saved.sourceFileCount} source files and ${saved.exportFileCount} ${exportLabel} to ${saved.directoryLabel}.${warningHint}`);
  renderTiles(payload.files.map((file) => ({ provider: file.provider, dataset: file.dataset, tileId: file.tile_id, path: file.saved_path })), context.document);
  await maybeOpenOutputFolder(context);
}

function hasMissingDownloads(payload) {
  return Boolean(payload.failed_downloads?.length);
}

function exportProfileLabel(exportProfile) {
  if (exportProfile === "ellipse_semantic_grc") return "separate building + tree GRC exports";
  if (exportProfile === "ellipse_mapinfo_tab") return "UTM32N GeoTIFF + TAB exports";
  if (exportProfile === "ellipse_mapinfo_tab_pyramids") return "UTM32N GeoTIFF + TAB + pyramid exports";
  return "GRD exports";
}

export function missingDownloadSummary(failures) {
  const shown = failures.slice(0, 8).map((failure) => `${failure.provider}/${failure.dataset}/${failure.tile_id || "unnamed-tile"}`);
  const extra = failures.length > shown.length ? ` and ${failures.length - shown.length} more` : "";
  return `Missing ${failures.length} identified file(s): ${shown.join(", ")}${extra}.`;
}

export function missingDownloadPrompt(failures) {
  return `${missingDownloadSummary(failures)}\n\nRetry the missing files now? Choose Cancel to stop without saving an incomplete export.`;
}

async function maybeOpenOutputFolder(context) {
  if (!(context.openFolderAfterDownload.checked && context.state.lastDownloadedOutputDir)) return;
  try {
    await openDownloadedOutputFolder(context.apiBaseUrl, context.state.lastDownloadedOutputDir, context.fetch);
  } catch (_error) {
    context.downloadStatus.textContent += " Could not open the output folder automatically.";
  }
}

function handlePreviewSubset(context, payload) {
  const summary = payload.results.map((result) => `${result.provider || payload.provider}/${result.dataset}: ${result.match_count} tiles`).join(" - ");
  const warningHint = payload.warnings?.length ? ` Warnings: ${payload.warnings.join("; ")}.` : "";
  setStatus(context, `${summary}. ${estimateText(payload)}${warningHint}`);
  renderTiles(payload.results.flatMap((result) => result.tiles.map((tile) => ({ provider: tile.provider, dataset: result.dataset, tileId: tile.tile_id, path: tile.primary_url }))), context.document);
}

function openDownloadedOutputFolder(apiBaseUrl, outputDir, fetchFn) {
  return fetchFn.call(globalThis, `${apiBaseUrl}/api/v1/subsets/open-folder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: outputDir }),
  });
}
