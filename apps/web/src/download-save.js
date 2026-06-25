const DOWNLOAD_DIRECTORY_DB = "multiplanner-downloads";
const DOWNLOAD_DIRECTORY_STORE = "handles";
const LAST_DOWNLOAD_DIRECTORY_KEY = "last-download-directory";

function basename(path) {
  const normalized = path.replaceAll("\\", "/");
  return normalized.slice(normalized.lastIndexOf("/") + 1) || "download.bin";
}

function openDownloadDirectoryDb() {
  return new Promise((resolve, reject) => {
    if (!window.indexedDB) {
      resolve(null);
      return;
    }

    const request = window.indexedDB.open(DOWNLOAD_DIRECTORY_DB, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(DOWNLOAD_DIRECTORY_STORE);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function readStoredDirectoryHandle() {
  try {
    const db = await openDownloadDirectoryDb();
    if (!db) return null;

    return await new Promise((resolve, reject) => {
      const transaction = db.transaction(DOWNLOAD_DIRECTORY_STORE, "readonly");
      const store = transaction.objectStore(DOWNLOAD_DIRECTORY_STORE);
      const request = store.get(LAST_DOWNLOAD_DIRECTORY_KEY);
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error);
    });
  } catch (_error) {
    return null;
  }
}

async function rememberDirectoryHandle(directoryHandle) {
  try {
    const db = await openDownloadDirectoryDb();
    if (!db) return;

    await new Promise((resolve, reject) => {
      const transaction = db.transaction(DOWNLOAD_DIRECTORY_STORE, "readwrite");
      const store = transaction.objectStore(DOWNLOAD_DIRECTORY_STORE);
      const request = store.put(directoryHandle, LAST_DOWNLOAD_DIRECTORY_KEY);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  } catch (_error) {
    // Remembering the folder is best-effort; the selected handle is still usable now.
  }
}

async function hasReadWritePermission(directoryHandle) {
  const options = { mode: "readwrite" };
  if ((await directoryHandle.queryPermission(options)) === "granted") {
    return true;
  }

  return (await directoryHandle.requestPermission(options)) === "granted";
}

async function canReuseDirectoryHandle(directoryHandle) {
  try {
    return await hasReadWritePermission(directoryHandle);
  } catch (_error) {
    return false;
  }
}

async function writeBlobToFile(directoryHandle, filename, blob) {
  const fileHandle = await directoryHandle.getFileHandle(filename, { create: true });
  const writable = await fileHandle.createWritable();
  try {
    await writable.write(blob);
  } finally {
    await writable.close();
  }
}

async function fetchCachedFile(apiBaseUrl, cachedPath) {
  const response = await fetch(`${apiBaseUrl}/api/v1/subsets/file?path=${encodeURIComponent(cachedPath)}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch cached file: ${cachedPath}`);
  }
  return response.blob();
}

export async function chooseDownloadDirectory() {
  if (!window.showDirectoryPicker) {
    throw new Error("This browser does not support folder picking.");
  }

  // Always show the picker — stored handle is used only as the starting location hint.
  const previousDirectoryHandle = await readStoredDirectoryHandle();
  let directoryHandle;
  try {
    directoryHandle = await window.showDirectoryPicker({
      mode: "readwrite",
      startIn: previousDirectoryHandle || "downloads",
    });
  } catch (error) {
    if (!previousDirectoryHandle) throw error;
    // Stale handle rejected by browser as startIn — retry with the well-known downloads folder.
    directoryHandle = await window.showDirectoryPicker({ mode: "readwrite", startIn: "downloads" });
  }

  await rememberDirectoryHandle(directoryHandle);
  return directoryHandle;
}

export async function saveSubsetPayloadToDirectory(apiBaseUrl, payload, rootDirectoryHandle) {
  const selectionName = payload.selection_name || "subset";
  const selectionDirectory = await rootDirectoryHandle.getDirectoryHandle(selectionName, { create: true });
  const groupByProvider = payload.provider === "auto";

  for (const file of payload.files) {
    const providerDirectory = groupByProvider
      ? await selectionDirectory.getDirectoryHandle(file.provider || "unknown-provider", { create: true })
      : selectionDirectory;
    const datasetDirectory = await providerDirectory.getDirectoryHandle(file.dataset, { create: true });
    const blob = await fetchCachedFile(apiBaseUrl, file.saved_path);
    await writeBlobToFile(datasetDirectory, basename(file.saved_path), blob);
  }

  const exportDirectory = await selectionDirectory.getDirectoryHandle("utm32", { create: true });
  for (const exportPath of payload.exports) {
    const blob = await fetchCachedFile(apiBaseUrl, exportPath);
    await writeBlobToFile(exportDirectory, basename(exportPath), blob);
  }

  return {
    rootName: rootDirectoryHandle.name,
    selectionName,
    sourceFileCount: payload.files.length,
    exportFileCount: payload.exports.length,
  };
}
