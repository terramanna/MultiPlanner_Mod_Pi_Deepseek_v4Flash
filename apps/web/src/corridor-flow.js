import {
  buildCorridorSubsetRequest,
  formatCorridorDownloadStatus,
  formatCorridorPreviewStatus,
  largeDownloadWarning,
  shouldWarnAboutLargeDownload,
} from "./corridor-subsets.js";
import { chooseDownloadDirectory, saveSubsetPayloadToDirectory } from "./download-save.js";

export function createCorridorFlow(context) {
  return {
    locate: () => locateCorridorSubsets(context),
    download: () => downloadCorridorSubsets(context),
    openLastDownloadedFolder: () => openLastDownloadedFolder(context),
  };
}

async function locateCorridorSubsets(context) {
  if (!ensureCorridorSelection(context)) return;
  context.lookupStatus.textContent = "querying provider";
  try {
    context.lookupStatus.textContent = formatCorridorPreviewStatus(await requestSubsetPreview(context));
  } catch (_error) {
    context.lookupStatus.textContent = "subset lookup failed";
  }
}

async function downloadCorridorSubsets(context) {
  if (!ensureCorridorSelection(context)) return;
  context.lookupStatus.textContent = "downloading selected subset tiles";
  try {
    await runCorridorDownload(context);
  } catch (_error) {
    context.lookupStatus.textContent = "subset download failed";
  }
}

async function runCorridorDownload(context) {
  const previewPayload = await requestSubsetPreview(context);
  if (shouldWarnAboutLargeDownload(previewPayload) && !window.confirm(largeDownloadWarning(previewPayload))) {
    context.lookupStatus.textContent = "download cancelled";
    return;
  }
  const rootDirectoryHandle = await chooseDownloadDirectory();
  const payload = await requestSubsetDownload(context);
  const saved = await saveSubsetPayloadToDirectory(context.apiBaseUrl, payload, rootDirectoryHandle);
  context.state.lastDownloadedOutputDir = payload.output_dir || null;
  context.btnOpenDownloadFolder.hidden = !context.state.lastDownloadedOutputDir;
  context.lookupStatus.textContent = formatCorridorDownloadStatus(saved, payload);
  await openOutputFolderAfterDownload(context, saved, payload);
}

async function openOutputFolderAfterDownload(context, saved, payload) {
  if (!(context.state.lastDownloadedOutputDir && context.openFolderAfterDownload.checked)) return;
  const status = formatCorridorDownloadStatus(saved, payload);
  try {
    await openDownloadedOutputFolder(context, context.state.lastDownloadedOutputDir);
    context.lookupStatus.textContent = `${status} Opened output folder.`;
  } catch (_openError) {
    context.lookupStatus.textContent = `${status} Saved, but could not open the output folder.`;
  }
}

function ensureCorridorSelection(context) {
  if (!context.state.apiReady) {
    context.lookupStatus.textContent = "backend still starting";
    return false;
  }
  if (!(context.state.siteA && context.state.siteB)) {
    context.lookupStatus.textContent = "set both sites first";
    return false;
  }
  return true;
}

async function requestSubsetPreview(context) {
  return requestSubset(context, "/api/v1/subsets/locate", 10000);
}

async function requestSubsetDownload(context) {
  return requestSubset(context, "/api/v1/subsets/download", 30000);
}

async function requestSubset(context, endpoint, timeoutMs) {
  const response = await context.fetchWithTimeout(`${context.apiBaseUrl}${endpoint}`, {
    method: "POST",
    timeoutMs,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildCorridorSubsetRequest(context.state.siteA, context.state.siteB, selectedExportProfile())),
  });
  if (!response.ok) throw new Error("subset request failed");
  return response.json();
}

function selectedExportProfile(doc = document) {
  return doc.querySelector('input[name="downloadExportProfile"]:checked')?.value || "ellipse_grd";
}

async function openLastDownloadedFolder(context) {
  if (!context.state.lastDownloadedOutputDir) {
    context.lookupStatus.textContent = "No downloaded output folder to open yet.";
    return;
  }
  try {
    await openDownloadedOutputFolder(context, context.state.lastDownloadedOutputDir);
    context.lookupStatus.textContent = `Opened output folder for ${folderName(context.state.lastDownloadedOutputDir)}.`;
  } catch (_error) {
    context.lookupStatus.textContent = "Could not open the output folder.";
  }
}

async function openDownloadedOutputFolder(context, outputDir) {
  const response = await context.fetchWithTimeout(`${context.apiBaseUrl}/api/v1/subsets/open-folder`, {
    method: "POST",
    timeoutMs: 10000,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: outputDir }),
  });
  if (!response.ok) throw new Error("open-folder request failed");
  return response.json();
}

function folderName(path) {
  return path.replaceAll("\\", "/").split("/").pop() || "download";
}
