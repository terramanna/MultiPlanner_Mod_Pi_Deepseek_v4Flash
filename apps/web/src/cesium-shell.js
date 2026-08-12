export function renderCesiumShell(useWorldTerrain) {
  return `
    <div class="shell">
      <aside class="panel panel-left">
        <div class="eyebrow">MultiPlanner</div>
        <h1>Local-first terrain planning</h1>
        <p class="lede">
          First cut: place two sites, keep the UI local, and wire the map shell
          to the backend contracts that drive subset fetch and LOS.
        </p>
        <div class="actions">
          <button id="btnSiteA">Mark Site A</button>
          <button id="btnSiteB">Mark Site B</button>
          <button id="btnCenter" class="button-ghost">Center active site</button>
          <button id="btnClear" class="button-ghost">Clear</button>
        </div>
        <div class="search-panel">
          <label class="field-label" for="searchInput">Search place or coordinates</label>
          <div class="search-row">
            <input id="searchInput" type="text" placeholder="52.324784, 7.467435 or street, city, business" />
            <button id="btnSearch" class="button-ghost">Find</button>
          </div>
          <div id="searchStatus" class="lookup-status">search will place the active site</div>
          <div id="searchResults" class="search-results"></div>
        </div>
        <dl class="facts">
          <div><dt>API</dt><dd id="apiStatus">checking</dd></div>
          <div><dt>Provider mode</dt><dd id="providerMode">loading</dd></div>
          <div><dt>Selection</dt><dd id="selectionMode">Site A</dd></div>
          <div><dt>Terrain mode</dt><dd id="terrainMode">${useWorldTerrain ? "world terrain" : "fast local"}</dd></div>
        </dl>
        <div class="site-readout">
          <div><span>Site A</span><strong id="siteAValue">not set</strong></div>
          <div><span>Site B</span><strong id="siteBValue">not set</strong></div>
        </div>
        ${lookupPanelHtml()}
      </aside>
      <section class="map-stage">
        <div id="cesiumContainer"></div>
        <div class="hud">
          <div class="hud-card">
            <div class="hud-label">Next build target</div>
            <div class="hud-value">subset fetch + LOS</div>
          </div>
          <div class="hud-card">
            <div class="hud-label">Backend</div>
            <div class="hud-value">FastAPI localhost</div>
          </div>
        </div>
      </section>
    </div>
  `;
}

function lookupPanelHtml() {
  return `
    <div class="lookup-panel">
      <button id="btnLocate" class="button-ghost">Preview corridor subsets</button>
      <button id="btnDownload" class="button-ghost">Keep subset tiles</button>
      <fieldset class="download-options">
        <legend>Export format</legend>
        <label><input type="radio" name="downloadExportProfile" value="ellipse_grd" checked /> GRD</label>
        <label><input type="radio" name="downloadExportProfile" value="ellipse_mapinfo_tab" /> UTM32N GeoTIFF + TAB</label>
        <label><input type="radio" name="downloadExportProfile" value="ellipse_mapinfo_tab_pyramids" /> UTM32N GeoTIFF + TAB + pyramids</label>
      </fieldset>
      <label class="download-open-toggle"><input id="openFolderAfterDownload" type="checkbox" checked /> Open output folder after download</label>
      <button id="btnOpenDownloadFolder" class="button-ghost download-open-link" type="button" hidden>Open last output folder</button>
      <div id="lookupStatus" class="lookup-status">waiting for two sites</div>
    </div>
  `;
}
