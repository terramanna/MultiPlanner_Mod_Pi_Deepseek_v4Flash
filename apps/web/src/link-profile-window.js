const DEFAULT_PROFILE_SETTINGS = {
  source: "dgm1_dom1",
  antennaHeightM: 30,
  frequencyMhz: 6000,
  fresnelZone: 1,
  sampleCount: 33,
};

const PROFILE_SOURCES = [
  { value: "dgm1", label: "DGM", detail: "terrain", datasets: ["dgm1"] },
  { value: "dom1", label: "DOM", detail: "surface", datasets: ["dom1"] },
  { value: "dgm1_dom1", label: "DGM + DOM", detail: "combined", datasets: ["dgm1", "dom1"] },
];

const SVG_WIDTH = 640;
const SVG_HEIGHT = 260;
const CHART = { left: 48, top: 24, right: 20, bottom: 38 };

export function createLinkProfileWindow({ parent = document.body, apiBaseUrl = "", fetchWithTimeout = fetch } = {}) {
  const root = document.createElement("section");
  root.className = "link-profile-window";
  root.hidden = true;
  root.setAttribute("role", "dialog");
  root.setAttribute("aria-label", "Link profile settings");
  root.innerHTML = profileWindowHtml();
  parent.appendChild(root);

  const controls = collectProfileControls(root);
  let link = null;
  bindProfileEvents(root, controls, {
    update: () => updateProfile(root, controls, link),
    calculate: () => calculatePathProfile(root, controls, link, apiBaseUrl, fetchWithTimeout),
  });

  return {
    open: (nextLink) => {
      link = nextLink;
      syncProfileSources(controls, nextLink.availableDatasets);
      root.hidden = false;
      updateProfile(root, controls, link);
      controls.antennaHeight.focus();
    },
    close: () => {
      root.hidden = true;
    },
    destroy: () => {
      root.remove();
    },
  };
}

export function profileSourceOptions(availableDatasets) {
  const available = new Set(availableDatasets);
  return PROFILE_SOURCES.map((source) => ({
    ...source,
    available: source.datasets.every((dataset) => available.has(dataset)),
  }));
}

export function fresnelRadiusMeters(distanceM, frequencyMhz, zone = 1, ratio = 0.5) {
  const safeFrequency = positiveNumber(frequencyMhz, DEFAULT_PROFILE_SETTINGS.frequencyMhz);
  const safeZone = Math.max(1, Math.round(positiveNumber(zone, 1)));
  const wavelengthM = 299792458 / (safeFrequency * 1_000_000);
  const firstLeg = distanceM * ratio;
  const secondLeg = distanceM - firstLeg;
  return Math.sqrt((safeZone * wavelengthM * firstLeg * secondLeg) / distanceM);
}

export function gigahertzToMegahertz(value) {
  return positiveNumber(value, DEFAULT_PROFILE_SETTINGS.frequencyMhz / 1000) * 1000;
}

export function linkDistanceMeters(siteA, siteB) {
  const radiusM = 6371000;
  const deltaLat = toRadians(siteB.lat - siteA.lat);
  const deltaLon = toRadians(siteB.lon - siteA.lon);
  const firstLat = toRadians(siteA.lat);
  const secondLat = toRadians(siteB.lat);
  const haversine = Math.sin(deltaLat / 2) ** 2
    + Math.cos(firstLat) * Math.cos(secondLat) * Math.sin(deltaLon / 2) ** 2;
  return 2 * radiusM * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
}

export function buildPathProfileRequest(link, settings) {
  return {
    provider: "auto",
    source: settings.source,
    site_a: profileEndpoint(link.siteA),
    site_b: profileEndpoint(link.siteB),
    antenna_height_m: settings.antennaHeightM,
    frequency_mhz: settings.frequencyMhz,
    fresnel_zone: Math.round(settings.fresnelZone),
    sample_count: DEFAULT_PROFILE_SETTINGS.sampleCount,
  };
}

function profileWindowHtml() {
  return `
    <div class="profile-header">
      <div>
        <div class="profile-kicker">Link profile</div>
        <h2>Site A to Site B</h2>
      </div>
      <button class="profile-close button-ghost" type="button" aria-label="Close profile">x</button>
    </div>
    <div class="profile-summary">
      <span id="profileDistance">0 km</span>
      <span id="profileMidFresnel">F1 midpoint 0 m</span>
    </div>
    <fieldset class="profile-source-options">
      <legend>Profile source</legend>
      ${PROFILE_SOURCES.map(sourceOptionHtml).join("")}
    </fieldset>
    <div class="profile-control-grid">
      <label>
        <span>Antenna height</span>
        <input id="profileAntennaHeight" type="number" min="0" max="250" step="0.5" value="30" />
      </label>
      <label>
        <span>Frequency GHz</span>
        <input id="profileFrequency" type="number" min="0.001" max="100" step="0.1" value="6" />
      </label>
      <label>
        <span>Fresnel zone</span>
        <select id="profileFresnelZone">
          <option value="1">F1</option>
          <option value="2">F2</option>
          <option value="3">F3</option>
          <option value="4">F4</option>
        </select>
      </label>
    </div>
    <button id="btnCalculateProfile" class="profile-calculate" type="button">Calculate profile</button>
    <svg id="profileChart" class="profile-chart" viewBox="0 0 ${SVG_WIDTH} ${SVG_HEIGHT}" role="img"></svg>
    <div id="profileStatus" class="profile-status"></div>
  `;
}

function sourceOptionHtml(source) {
  const checked = source.value === DEFAULT_PROFILE_SETTINGS.source ? "checked" : "";
  return `
    <label>
      <input type="radio" name="profileSource" value="${source.value}" ${checked} />
      <span>${source.label}</span>
      <small>${source.detail}</small>
    </label>
  `;
}

function collectProfileControls(root) {
  return {
    close: root.querySelector(".profile-close"),
    sourceInputs: Array.from(root.querySelectorAll('input[name="profileSource"]')),
    antennaHeight: root.querySelector("#profileAntennaHeight"),
    frequency: root.querySelector("#profileFrequency"),
    fresnelZone: root.querySelector("#profileFresnelZone"),
    distance: root.querySelector("#profileDistance"),
    midFresnel: root.querySelector("#profileMidFresnel"),
    calculate: root.querySelector("#btnCalculateProfile"),
    chart: root.querySelector("#profileChart"),
    status: root.querySelector("#profileStatus"),
  };
}

function bindProfileEvents(root, controls, actions) {
  controls.close.addEventListener("click", () => {
    root.hidden = true;
  });
  controls.calculate.addEventListener("click", actions.calculate);
  root.addEventListener("input", actions.update);
  root.addEventListener("change", actions.update);
}

function syncProfileSources(controls, availableDatasets) {
  const options = profileSourceOptions(availableDatasets);
  for (const input of controls.sourceInputs) {
    const option = options.find((entry) => entry.value === input.value);
    input.disabled = !option?.available;
    input.closest("label").classList.toggle("is-disabled", input.disabled);
  }
  if (!controls.sourceInputs.some((input) => input.checked && !input.disabled)) {
    controls.sourceInputs.find((input) => !input.disabled).checked = true;
  }
}

function updateProfile(root, controls, link) {
  if (!link) return;
  const settings = readProfileSettings(controls);
  const profile = buildProfilePreview(link.siteA, link.siteB, settings);
  controls.distance.textContent = formatDistance(profile.distanceM);
  controls.midFresnel.textContent = `${settings.fresnelZoneLabel} midpoint ${profile.midFresnelM.toFixed(1)} m`;
  controls.chart.innerHTML = renderProfileChart(profile, settings);
  controls.status.textContent = profileStatusText(root, settings.source);
}

async function calculatePathProfile(root, controls, link, apiBaseUrl, fetchWithTimeout) {
  if (!link) return;
  const settings = readProfileSettings(controls);
  controls.calculate.disabled = true;
  controls.status.textContent = "calculating sampled path profile";
  try {
    const profile = await requestPathProfile(apiBaseUrl, fetchWithTimeout, link, settings);
    renderSampledProfile(root, controls, profile, settings);
  } catch (_error) {
    controls.status.textContent = "path profile calculation failed; showing local Fresnel preview";
  } finally {
    controls.calculate.disabled = false;
  }
}

async function requestPathProfile(apiBaseUrl, fetchWithTimeout, link, settings) {
  const response = await fetchWithTimeout(`${apiBaseUrl}/api/v1/profile/path`, {
    method: "POST",
    timeoutMs: 60000,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildPathProfileRequest(link, settings)),
  });
  if (!response.ok) throw new Error("path profile request failed");
  return response.json();
}

function renderSampledProfile(root, controls, payload, settings) {
  const profile = profileFromBackendPayload(payload);
  controls.distance.textContent = formatDistance(payload.distance_m);
  controls.midFresnel.textContent = `${settings.fresnelZoneLabel} midpoint ${profile.midFresnelM.toFixed(1)} m`;
  controls.chart.innerHTML = renderProfileChart(profile, settings);
  controls.status.textContent = sampledProfileStatus(root, settings.source, payload);
}

function readProfileSettings(controls) {
  const source = controls.sourceInputs.find((input) => input.checked)?.value || DEFAULT_PROFILE_SETTINGS.source;
  const fresnelZone = positiveNumber(controls.fresnelZone.value, DEFAULT_PROFILE_SETTINGS.fresnelZone);
  return {
    source,
    antennaHeightM: positiveNumber(controls.antennaHeight.value, DEFAULT_PROFILE_SETTINGS.antennaHeightM),
    frequencyMhz: gigahertzToMegahertz(controls.frequency.value),
    fresnelZone,
    fresnelZoneLabel: `F${Math.round(fresnelZone)}`,
  };
}

function buildProfilePreview(siteA, siteB, settings) {
  const distanceM = Math.max(1, linkDistanceMeters(siteA, siteB));
  const startM = elevation(siteA) + settings.antennaHeightM;
  const endM = elevation(siteB) + settings.antennaHeightM;
  const midFresnelM = fresnelRadiusMeters(distanceM, settings.frequencyMhz, settings.fresnelZone);
  const samples = Array.from({ length: 33 }, (_, index) => profileSample(index, distanceM, startM, endM, settings));
  return { distanceM, midFresnelM, samples, startM, endM };
}

function profileFromBackendPayload(payload) {
  const samples = payload.samples.map((sample) => ({
    ratio: sample.ratio,
    linkM: sample.los_height_m,
    upperM: sample.los_height_m + sample.fresnel_radius_m,
    lowerM: sample.fresnel_lower_m,
    terrainM: sample.selected_height_m,
  }));
  const midpoint = samples[Math.floor(samples.length / 2)];
  return {
    distanceM: payload.distance_m,
    midFresnelM: payload.samples[Math.floor(payload.samples.length / 2)].fresnel_radius_m,
    samples,
    startM: samples[0].linkM,
    endM: samples[samples.length - 1].linkM,
    minimumClearanceM: minimumClearance(payload.samples),
    midpointTerrainM: midpoint.terrainM,
  };
}

function profileSample(index, distanceM, startM, endM, settings) {
  const ratio = index / 32;
  const linkM = startM + (endM - startM) * ratio;
  const fresnelM = fresnelRadiusMeters(distanceM, settings.frequencyMhz, settings.fresnelZone, ratio);
  return { ratio, linkM, upperM: linkM + fresnelM, lowerM: linkM - fresnelM };
}

function renderProfileChart(profile, settings) {
  const scale = chartScale(profile.samples);
  const lower = pathFor(profile.samples, scale, (sample) => sample.lowerM);
  const upper = pathFor([...profile.samples].reverse(), scale, (sample) => sample.upperM);
  const link = pathFor(profile.samples, scale, (sample) => sample.linkM);
  const terrain = terrainPath(profile.samples, scale);
  return `
    <path class="profile-fresnel-fill" d="${upper} L ${lower.slice(2)} Z"></path>
    <path class="profile-fresnel-line" d="${upper}"></path>
    <path class="profile-fresnel-line" d="${lower}"></path>
    <path class="profile-link-line" d="${link}"></path>
    ${terrain ? `<path class="profile-terrain-line" d="${terrain}"></path>` : ""}
    ${axisLabels(profile, settings, scale)}
  `;
}

function chartScale(samples) {
  const values = samples.flatMap((sample) => [sample.upperM, sample.lowerM, sample.terrainM])
    .filter((value) => Number.isFinite(value));
  const min = Math.min(...values) - 5;
  const max = Math.max(...values) + 5;
  return {
    min,
    max,
    x: (ratio) => CHART.left + ratio * (SVG_WIDTH - CHART.left - CHART.right),
    y: (value) => CHART.top + (max - value) / (max - min) * (SVG_HEIGHT - CHART.top - CHART.bottom),
  };
}

function terrainPath(samples, scale) {
  const terrainSamples = samples.filter((sample) => Number.isFinite(sample.terrainM));
  return terrainSamples.length > 1 ? pathFor(terrainSamples, scale, (sample) => sample.terrainM) : "";
}

function pathFor(samples, scale, readValue) {
  return samples.map((sample, index) => {
    const command = index === 0 ? "M" : "L";
    return `${command} ${scale.x(sample.ratio).toFixed(1)} ${scale.y(readValue(sample)).toFixed(1)}`;
  }).join(" ");
}

function axisLabels(profile, settings, scale) {
  const bottom = SVG_HEIGHT - 12;
  return `
    <line class="profile-axis" x1="${CHART.left}" y1="${SVG_HEIGHT - CHART.bottom}" x2="${SVG_WIDTH - CHART.right}" y2="${SVG_HEIGHT - CHART.bottom}"></line>
    <text x="${CHART.left}" y="${bottom}">Site A</text>
    <text x="${SVG_WIDTH - CHART.right - 44}" y="${bottom}">Site B</text>
    <text x="${SVG_WIDTH / 2 - 60}" y="${bottom}">${formatDistance(profile.distanceM)}</text>
    <text x="${CHART.left}" y="16">${settings.fresnelZoneLabel} at ${(settings.frequencyMhz / 1000).toFixed(1)} GHz</text>
    <text x="${SVG_WIDTH - 150}" y="16">${settings.antennaHeightM.toFixed(1)} m antenna</text>
    <text x="${CHART.left}" y="${scale.y(profile.startM).toFixed(1) - 8}">LOS</text>
  `;
}

function profileStatusText(root, source) {
  const label = root.querySelector(`input[value="${source}"]`)?.closest("label")?.querySelector("span")?.textContent || "profile";
  return `${label} selected. Calculate profile to sample raster heights.`;
}

function sampledProfileStatus(root, source, payload) {
  const label = root.querySelector(`input[value="${source}"]`)?.closest("label")?.querySelector("span")?.textContent || "profile";
  const clearance = minimumClearance(payload.samples);
  const warnings = payload.warnings?.length ? ` ${payload.warnings.length} sample warnings.` : "";
  return `${label} sampled: minimum clearance ${formatClearance(clearance)}.${warnings}`;
}

function minimumClearance(samples) {
  const values = samples.map((sample) => sample.clearance_m).filter((value) => Number.isFinite(value));
  return values.length ? Math.min(...values) : null;
}

function formatClearance(value) {
  return Number.isFinite(value) ? `${value.toFixed(1)} m` : "not available";
}

function formatDistance(distanceM) {
  return distanceM >= 1000 ? `${(distanceM / 1000).toFixed(2)} km` : `${distanceM.toFixed(0)} m`;
}

function elevation(site) {
  return Number.isFinite(site.height) ? site.height : 0;
}

function profileEndpoint(site) {
  return {
    lon: site.lon,
    lat: site.lat,
    height_m: elevation(site),
  };
}

function positiveNumber(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : fallback;
}

function toRadians(degrees) {
  return degrees * Math.PI / 180;
}
