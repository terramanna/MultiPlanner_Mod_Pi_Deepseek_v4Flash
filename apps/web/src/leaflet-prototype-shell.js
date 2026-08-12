const defaultProviders = [
  { name: "auto", label: "Auto (split by provider)" },
  { name: "lgln-ni", label: "Niedersachsen LGLN" },
  { name: "geobasis-nrw", label: "NRW Geobasis" },
  { name: "geosn-sn", label: "Saxony GeoSN" },
  { name: "hvbg-he", label: "Hessen HVBG" },
  { name: "lvermgeo-st", label: "Saxony-Anhalt LVermGeo" },
  { name: "geobasis-bb", label: "Brandenburg Geobasis" },
  { name: "lgl-bw", label: "Baden-Wuerttemberg LGL" },
  { name: "ldbv-by", label: "Bayern LDBV" },
  { name: "lgv-hh", label: "Hamburg LGV" },
];

const labels = {
  corridor: "A - Two sites / corridor",
  area: "B - Draw rectangular area",
  point: "C - Single point",
};

export function renderPrototypeShell(variant) {
  return `<main class="leaflet-prototype-shell">
    ${renderPanel(variant)}
    ${renderMapSection()}
    ${renderVariantSwitcher(variant)}
  </main>`;
}

function renderPanel(variant) {
  return `<aside class="leaflet-prototype-panel">
    ${renderIntro(variant)}
    ${renderSearch()}
    ${renderProviderControls()}
    ${renderSelection()}
    ${renderProbeControls()}
    ${renderDownloadControls()}
  </aside>`;
}

function renderIntro(variant) {
  return `<div class="prototype-kicker">PROTOTYPE - 2D local planning</div>
    <h1>${labels[variant]}</h1>
    <p id="modeHelp" class="prototype-help"></p>
    <div class="prototype-actions" id="placementActions"></div>`;
}

function renderSearch() {
  return `<label for="searchInput">Search place or coordinates</label>
    <div class="prototype-search-row">
      <input id="searchInput" placeholder="52.324784, 7.467435 or address" />
      <button id="searchButton">Find</button>
    </div>
    <div id="searchStatus" class="prototype-status">API: starting</div>
    <div id="searchResults" class="prototype-results"></div>`;
}

function renderProviderControls() {
  return `<label for="providerSelect">Data provider</label>
    <div class="prototype-search-row">
    <select id="providerSelect">${providerOptions()}</select>
      <select id="providerSortSelect" aria-label="Sort providers">
        <option value="asc" selected>A to Z</option>
        <option value="desc">Z to A</option>
      </select>
    </div>
    <label for="jobNameInput">Job / file name</label>
    <input id="jobNameInput" placeholder="01wzoming01_2km_diam_1m_res" />
    <label class="prototype-coverage-toggle"><input id="coverageToggle" type="checkbox" checked /> Show selected provider coverage</label>
    <label class="prototype-coverage-toggle"><input id="networkToggle" type="checkbox" /> Show network overlay</label>
    <div id="networkFilterWrap" class="prototype-network-filter" hidden>
      <input id="networkFilter" placeholder="Filter by site or link name…" />
    </div>
    <fieldset id="datasetChoices" class="prototype-datasets"></fieldset>`;
}

function renderSelection() {
  return `<section class="prototype-selection">
      <h2>Current selection</h2>
      <pre id="selectionReadout">none</pre>
    </section>`;
}

function renderProbeControls() {
  return `<section class="prototype-probe">
    <h2>Point probe</h2>
    <label for="probeDataset">Probe type</label>
    <select id="probeDataset">
      <option value="multi">DGM + DOM + nDOM</option>
      <option value="dgm1">DGM only</option>
      <option value="dom1">DOM only</option>
      <option value="ndsm">nDOM only</option>
    </select>
    <div class="probe-mode-row">
      <label class="probe-mode-cell">
        <input type="checkbox" id="probeEnable">
        <span class="probe-mode-label">Enable</span>
      </label>
      <label class="probe-mode-cell">
        <input type="radio" name="protoProbeMode" value="hover" id="probeModeHover">
        <span class="probe-mode-label">Hover</span>
      </label>
      <label class="probe-mode-cell">
        <input type="radio" name="protoProbeMode" value="manual" id="probeModeManual" checked>
        <span class="probe-mode-label">Manual</span>
      </label>
    </div>
    <button id="probeSampleNow" class="secondary" type="button" disabled>Sample now</button>
    <span id="probeStatus" class="prototype-status"></span>
  </section>`;
}

function renderDownloadControls() {
  return `<div class="prototype-actions prototype-download-actions">
      <button id="locateButton" class="secondary">Preview 1 m subset</button>
      <button id="downloadButton">Download + GRD export</button>
      <button id="clearButton" class="secondary">Clear selection</button>
    </div>
    ${renderExportOptions()}
    <label class="prototype-open-toggle"><input id="openFolderAfterDownload" type="checkbox" checked /> Open output folder after download</label>
    <button id="btnOpenDownloadFolder" class="prototype-open-folder" type="button" hidden>Open last output folder</button>
    <div id="downloadStatus" class="prototype-status">Choose a geometry on the map.</div>
    <progress id="downloadProgress" value="0" max="1" hidden></progress>
    <div id="tileList" class="prototype-tile-list"></div>
    <p class="prototype-note">Downloads use the existing provider API and respect the selected export format.</p>`;
}

function renderExportOptions() {
  return `<fieldset class="prototype-download-options">
      <legend>Export format</legend>
      <label><input type="radio" name="prototypeDownloadExportProfile" value="ellipse_grd" checked /> GRD</label>
      <label><input type="radio" name="prototypeDownloadExportProfile" value="ellipse_mapinfo_tab" /> UTM32N GeoTIFF + TAB</label>
      <label><input type="radio" name="prototypeDownloadExportProfile" value="ellipse_mapinfo_tab_pyramids" /> UTM32N GeoTIFF + TAB + pyramids</label>
    </fieldset>`;
}

function renderMapSection() {
  return `<section class="leaflet-prototype-map-wrap">
    <div id="leafletMap"></div>
    <div class="prototype-map-note">Use the layer button for street or satellite imagery. Draw tools select download areas.</div>
    <div id="measurementReadout" class="prototype-measurement">Draw a circle, rectangle, or lasso to see dimensions.</div>
  </section>`;
}

function renderVariantSwitcher(variant) {
  return `<nav class="prototype-switcher" aria-label="Prototype variants">
    <button id="previousVariant" aria-label="Previous variant">&lt;</button>
    <strong id="variantLabel">${labels[variant]}</strong>
    <button id="nextVariant" aria-label="Next variant">&gt;</button>
    <a href="?renderer=cesium">Open Cesium comparison</a>
  </nav>`;
}

function providerOptions() {
  const autoProvider = defaultProviders.find((provider) => provider.name === "auto");
  const sortedProviders = defaultProviders
    .filter((provider) => provider.name !== "auto")
    .slice()
    .sort((left, right) => left.label.localeCompare(right.label));
  const providers = autoProvider ? [autoProvider, ...sortedProviders] : sortedProviders;
  return providers.map((provider) => `<option value="${provider.name}">${provider.label}</option>`).join("");
}
