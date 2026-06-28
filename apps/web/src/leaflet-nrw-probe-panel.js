export function renderNrwProbeShell() {
  return `
    <div class="nrw-layout">
      <aside class="nrw-panel" id="nrwPanel">
        <section class="nrw-section">
          <label class="nrw-label" for="nrwLayerSelect">Map layer</label>
          <select id="nrwLayerSelect" class="nrw-select">
            <option value="dop">NRW DOP imagery</option>
            <option value="dgm1">NRW DGM1 hillshade (local)</option>
            <option value="dom1">NRW DOM1 grayscale (local)</option>
            <option value="ndsm">NRW nDSM colour (local)</option>
            <option value="streets">Streets (OSM)</option>
          </select>
        </section>
        <section class="nrw-section">
          <label class="nrw-label">Active layer opacity</label>
          <input id="nrwBaseOpacity" type="range" min="0" max="100" value="100" class="nrw-slider">
          <span id="nrwBaseOpacityVal" class="nrw-opacity-val">100%</span>
        </section>
        <section class="nrw-section nrw-box">
          <span class="nrw-box-title">DOM over ortho</span>
          <label class="nrw-check-row">
            <input type="checkbox" id="nrwDomOverlay">
            <span>Show DOM hillshade over NRW DOP</span>
          </label>
          <label class="nrw-label nrw-label-indent">DOM hillshade opacity</label>
          <input id="nrwDomOpacity" type="range" min="0" max="100" value="55" class="nrw-slider">
          <span id="nrwDomOpacityVal" class="nrw-opacity-val">55%</span>
        </section>
        <section class="nrw-section">
          <h3 class="nrw-heading">Point probe</h3>
          <label class="nrw-label" for="nrwProbeSource">Probe source</label>
          <select id="nrwProbeSource" class="nrw-select">
            <option value="multi">DGM1 + DOM1 + nDSM</option>
            <option value="dgm1">DGM1 only</option>
            <option value="dom1">DOM1 only</option>
            <option value="ndsm">nDSM only</option>
          </select>
          <div class="probe-mode-row">
            <label class="probe-mode-cell">
              <input type="checkbox" id="nrwProbeEnable">
              <span class="probe-mode-label">Enable probe</span>
            </label>
            <label class="probe-mode-cell">
              <input type="radio" name="nrwProbeMode" value="hover" id="nrwProbeModeHover">
              <span class="probe-mode-label">Hover</span>
            </label>
            <label class="probe-mode-cell">
              <input type="radio" name="nrwProbeMode" value="manual" id="nrwProbeModeManual" checked>
              <span class="probe-mode-label">Manual</span>
            </label>
          </div>
          <button id="nrwSampleNow" class="secondary">Sample now</button>
          <pre id="nrwProbeResult" class="nrw-probe-result"></pre>
        </section>
      </aside>
      <div id="nrwMap" class="nrw-map"></div>
    </div>
  `;
}

export function panelRefs() {
  return {
    layerSelect: document.getElementById("nrwLayerSelect"),
    baseOpacity: document.getElementById("nrwBaseOpacity"),
    baseOpacityVal: document.getElementById("nrwBaseOpacityVal"),
    domOverlay: document.getElementById("nrwDomOverlay"),
    domOpacity: document.getElementById("nrwDomOpacity"),
    domOpacityVal: document.getElementById("nrwDomOpacityVal"),
    probeSource: document.getElementById("nrwProbeSource"),
    probeEnable: document.getElementById("nrwProbeEnable"),
    sampleNow: document.getElementById("nrwSampleNow"),
    probeResult: document.getElementById("nrwProbeResult"),
  };
}
