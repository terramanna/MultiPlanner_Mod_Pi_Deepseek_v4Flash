import { chooseDownloadDirectory, saveSubsetPayloadToDirectory } from "./download-save.js";
import {
  apiGeometry,
  buildSelectionName,
  estimateText,
  largeDownloadWarning,
  renderTiles,
  selectedDatasets,
} from "./leaflet-prototype-utils.js";

export async function requestLeafletSubset(context, download) {
  const geometry = context.currentGeometry();
  if (!geometry) return setStatus(context, "Complete the selection first.");
  const datasets = selectedDatasets(context.document);
  if (!datasets.length) return setStatus(context, "Choose at least one dataset.");

  const body = buildSubsetRequestBody(context, download, geometry, datasets);
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
  context.downloadStatus.textContent = message;
}

function failureStatus(download, error) {
  const prefix = download ? "Download/export failed" : "Subset lookup failed";
  return error?.message ? `${prefix}: ${error.message}` : `${prefix}.`;
}

function buildSubsetRequestBody(context, download, geometry, datasets) {
  const body = { provider: context.state.provider, datasets, geometry: apiGeometry(geometry) };
  if (download) {
    body.selection_name = buildSelectionName(geometry, context.state, context.map, context.jobNameInput, context.providerCoverage);
    body.export_profile = context.selectedExportProfile();
  }
  return body;
}

async function prepareSubsetDownload(context, body) {
  const preview = await fetchSubsetPreview(context, body);
  const warning = largeDownloadWarning(preview);
  if (warning && !context.confirm(warning)) return setCancelled(context);
  setStatus(context, "Choose an output folder to start the download/export.");
  try {
    return await chooseDownloadDirectory();
  } catch (_error) {
    return setCancelled(context);
  }
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
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let payload = null;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop();
    for (const part of parts) {
      if (!part.startsWith("data: ")) continue;
      const event = JSON.parse(part.slice(6));
      if (event.type === "progress") {
        setStatus(context, `Downloading tile ${event.current} of ${event.total}…`);
      } else if (event.type === "done") {
        payload = event.result;
      } else if (event.type === "error") {
        throw new Error(event.message);
      }
    }
  }
  if (!payload) throw new Error("Download stream ended without result.");
  return handleDownloadSubset(context, body, payload, rootDirectoryHandle);
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
  const exportLabel = body.export_profile === "ellipse_mapinfo_tab" ? "UTM32N GeoTIFF + TAB exports" : "GRD exports";
  setStatus(context, `Saved ${saved.sourceFileCount} source files and ${saved.exportFileCount} ${exportLabel} to ${saved.rootName}\\${saved.selectionName}.${warningHint}`);
  renderTiles(payload.files.map((file) => ({ provider: file.provider, dataset: file.dataset, tileId: file.tile_id, path: file.saved_path })), context.document);
  await maybeOpenOutputFolder(context);
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
