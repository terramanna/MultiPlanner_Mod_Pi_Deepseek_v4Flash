export function renderNrwProbeShell() {
  return `
    <div class="nrw-layout">
      <aside class="nrw-panel" id="nrwPanel">
        <div class="nrw-header">
          <span class="nrw-title">Terrain Inspector</span>
          <span class="nrw-version">v1.0</span>
        </div>
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
          <span class="nrw-box-title">nDOM50 over ortho</span>
          <label class="nrw-check-row">
            <input type="checkbox" id="nrwNdomOverlay">
            <span>Show nDOM50 WMS over base layer</span>
          </label>
          <label class="nrw-label nrw-label-indent">nDOM50 opacity</label>
          <input id="nrwNdomOpacity" type="range" min="0" max="100" value="60" class="nrw-slider">
          <span id="nrwNdomOpacityVal" class="nrw-opacity-val">60%</span>
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
    ndomOverlay: document.getElementById("nrwNdomOverlay"),
    ndomOpacity: document.getElementById("nrwNdomOpacity"),
    ndomOpacityVal: document.getElementById("nrwNdomOpacityVal"),
    probeSource: document.getElementById("nrwProbeSource"),
    probeEnable: document.getElementById("nrwProbeEnable"),
    sampleNow: document.getElementById("nrwSampleNow"),
  };
}
