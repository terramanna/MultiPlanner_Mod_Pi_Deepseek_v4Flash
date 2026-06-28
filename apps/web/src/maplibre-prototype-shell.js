const labels = {
  corridor: "NRW corridor",
  area: "NRW area",
  point: "NRW point",
};
const prototypeVersion = "MapLibre NRW v2026-06-28-r1";

export function renderMapLibreShell(variant) {
  return `<main class="maplibre-prototype-shell">
    <aside class="maplibre-prototype-panel">
      <div class="prototype-kicker">PROTOTYPE - MapLibre NRW DOM</div>
      <div class="prototype-version">${prototypeVersion}</div>
      <h1>${labels[variant] || labels.corridor}</h1>
      <p class="prototype-help">This view is for NRW raster display checks. DOM here is the local tile endpoint backed by cached NRW source tiles, not a direct WCS stream.</p>
      <label for="baseLayerSelect">Map layer</label>
      <select id="baseLayerSelect">
        <option value="osm" selected>OpenStreetMap</option>
        <option value="nrw-dop">NRW DOP imagery</option>
        <option value="nrw-topo">NRW DTK topo</option>
        <option value="nrw-dtm">NRW DTM hillshade</option>
        <option value="nrw-dhm-overview">NRW DHM overview WMS</option>
        <option value="nrw-ndom50-wms">NRW nDOM50 WMS</option>
        <option value="nrw-dom1-local">NRW DOM1 local</option>
        <option value="nrw-dgm1-local">NRW DGM1 local</option>
        <option value="nrw-ndsm-local">NRW nDSM local</option>
      </select>
      <label for="activeLayerOpacity">Active layer opacity</label>
      <input id="activeLayerOpacity" type="range" min="0.15" max="1" step="0.05" value="1" />
      <div id="activeLayerOpacityReadout" class="prototype-overlay-readout">100%</div>
      <fieldset class="prototype-download-options prototype-overlay-controls">
        <legend>DOM over ortho</legend>
        <label><input id="domOverlayEnabled" type="checkbox" /> Show DOM hillshade over NRW DOP</label>
        <label for="domOverlayOpacity">DOM hillshade opacity</label>
        <input id="domOverlayOpacity" type="range" min="0.15" max="0.85" step="0.05" value="0.35" />
        <div id="domOverlayOpacityReadout" class="prototype-overlay-readout">35%</div>
      </fieldset>
      <section class="prototype-selection">
        <h2>Point probe</h2>
        <label for="probeTargetSelect">Probe source</label>
        <select id="probeTargetSelect">
          <option value="combined" selected>DGM1 + DOM1 + nDSM</option>
          <option value="dgm1">DGM1 only</option>
          <option value="dom1">DOM1 only</option>
          <option value="ndsm">nDSM only</option>
        </select>
        <div class="prototype-inline-options">
          <label><input id="probeEnabled" type="checkbox" checked /> Enable probe</label>
          <label><input type="radio" name="probeMode" value="hover" checked /> Hover</label>
          <label><input type="radio" name="probeMode" value="manual" /> Manual</label>
        </div>
        <button id="probeSampleButton" class="secondary" type="button">Sample now</button>
        <pre id="probeReadout" class="prototype-status">Move over the map to read DGM, DOM, and nDSM.</pre>
      </section>
      <section class="prototype-selection">
        <h2>Active layer status</h2>
        <pre id="layerStatus" class="prototype-status">Waiting for map.</pre>
      </section>
      <section class="prototype-selection">
        <h2>What this returns</h2>
        <p class="prototype-note"><code>/api/v1/tiles/geobasis-nrw/dom1/{z}/{x}/{y}.png</code> returns a rendered 256x256 grayscale PNG for the current Web Mercator tile.</p>
        <p class="prototype-note">The backend builds the tile from NRW DOM1 source TIFFs, caches it locally, and serves PNGs to MapLibre.</p>
        <p class="prototype-note"><code>NRW nDOM50 WMS</code> is the official NRW relative-height product. It shows height above terrain, not clutter identity or object class.</p>
        <p class="prototype-note">For a bare-ground point, <code>nDSM</code> should usually be near 0. For a roof or tree crown, <code>DOM1</code> should rise above <code>DGM1</code>, and <code>nDSM</code> should become positive.</p>
      </section>
      <section class="prototype-selection">
        <h2>NRW source matrix</h2>
        <div class="prototype-source-grid">
          <div class="prototype-source-cell prototype-source-head">Product</div>
          <div class="prototype-source-cell prototype-source-head">Meaning</div>
          <div class="prototype-source-cell prototype-source-head">Service path</div>
          <div class="prototype-source-cell"><code>DOM1 local</code></div>
          <div class="prototype-source-cell">Absolute surface elevation rendered from NRW DOM1 GeoTIFF.</div>
          <div class="prototype-source-cell"><code>opengeodata ... /dom1_tiff/</code><br /><code>/api/v1/tiles/geobasis-nrw/dom1/...</code></div>
          <div class="prototype-source-cell"><code>DOM WCS</code></div>
          <div class="prototype-source-cell">Official NRW DOM coverage service.</div>
          <div class="prototype-source-cell"><code>wcs_nw_dom</code></div>
          <div class="prototype-source-cell"><code>nDOM50 WMS</code></div>
          <div class="prototype-source-cell">Official NRW normalized surface model for relative height above terrain.</div>
          <div class="prototype-source-cell"><code>wms_nw_ndom</code></div>
          <div class="prototype-source-cell"><code>nDOM50 WCS</code></div>
          <div class="prototype-source-cell">Official NRW coverage form of the same relative-height product.</div>
          <div class="prototype-source-cell"><code>wcs_nw_ndom</code></div>
        </div>
      </section>
      <div class="prototype-actions">
        <button id="resetDomMetricsButton" class="secondary" type="button">Reset DOM metrics</button>
      </div>
      <p id="mapStatus" class="prototype-status">Map booting.</p>
    </aside>
    <section class="maplibre-prototype-map-wrap">
      <div id="maplibreMap"></div>
      <div class="prototype-map-note">Use the side panel to switch between NRW basemaps and the local DOM/DGM/nDSM tile endpoints.</div>
    </section>
    <nav class="prototype-switcher" aria-label="Prototype variants">
      <a href="?renderer=leaflet&variant=${variant}">Leaflet</a>
      <a href="?renderer=cesium">Cesium</a>
    </nav>
  </main>`;
}
