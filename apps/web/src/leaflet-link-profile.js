const DEFAULTS = {
  source: "dgm1_dom1",
  antennaAHeightM: 30,
  antennaBHeightM: 30,
  frequencyMhz: 6000,
  fresnelZone: 1,
  sampleCount: 25,
};

const SOURCES = [
  ["dgm1", "DGM"],
  ["dom1", "DOM"],
  ["dgm1_dom1", "DGM + DOM"],
];

const PROFILE_PROVIDER_BBOXES = [
  { provider: "lgl-bw", west: 7.51, south: 47.53, east: 10.49, north: 49.79 },
];

export function createLeafletLinkProfile({ L, map, apiBaseUrl, provider, fetchFn = fetch }) {
  return {
    openSites: (siteA, siteB, latlng) => openProfile({ L, map, apiBaseUrl, provider, fetchFn }, linkFromSites(siteA, siteB), latlng),
    openNetwork: (properties, latlng) => openProfile({ L, map, apiBaseUrl, provider, fetchFn }, linkFromNetwork(properties), latlng),
    close: () => map.closePopup(),
  };
}

export function buildLeafletPathProfileRequest(link, settings, provider = "auto") {
  const antennaAHeightM = antennaHeight(settings, "A");
  const antennaBHeightM = antennaHeight(settings, "B");
  return {
    provider: resolveProfileProvider(link, provider),
    source: settings.source,
    site_a: endpoint(link.siteA),
    site_b: endpoint(link.siteB),
    antenna_height_m: antennaAHeightM,
    antenna_a_height_m: antennaAHeightM,
    antenna_b_height_m: antennaBHeightM,
    frequency_mhz: settings.frequencyMhz,
    fresnel_zone: Math.round(settings.fresnelZone),
    sample_count: sampleCount(settings.sampleCount),
  };
}

export function resolveProfileProvider(link, selectedProvider = "auto") {
  if (selectedProvider && selectedProvider !== "auto") return selectedProvider;
  const mid = midpoint(link);
  return PROFILE_PROVIDER_BBOXES.find((bbox) => insideBbox(mid, bbox))?.provider || "auto";
}

function openProfile(context, link, latlng) {
  const content = profileContent(link);
  keepPopupInteractive(context.L, content);
  bindProfileControls(content, context, link);
  preloadProfile(content, context, link);
  context.L.popup({ maxWidth: 560, className: "leaflet-profile-popup", closeOnClick: false })
    .setLatLng(latlng || midpoint(link))
    .setContent(content)
    .openOn(context.map);
}

function preloadProfile(content, context, link) {
  content.querySelector(".leaflet-profile-status").textContent = "Loading sampled profile in the background...";
  window.setTimeout(() => { void calculateProfile(content, context, link); }, 0);
}

function keepPopupInteractive(L, content) {
  L.DomEvent.disableClickPropagation(content);
  L.DomEvent.disableScrollPropagation(content);
  content.addEventListener("pointerdown", (event) => event.stopPropagation());
}

function profileContent(link) {
  const div = document.createElement("div");
  div.className = "leaflet-profile";
  div.innerHTML = `
    <strong>${escapeHtml(link.label)}</strong>
    <div class="leaflet-profile-meta">${distanceLabel(link)} A to B</div>
    ${linkDetails(link)}
    <fieldset>${SOURCES.map(sourceRadio).join("")}</fieldset>
    <div class="leaflet-profile-grid">
      <label>Antenna A m<input data-profile="antenna-a" type="number" min="0" max="250" step="0.5" value="${DEFAULTS.antennaAHeightM}"></label>
      <label>Antenna B m<input data-profile="antenna-b" type="number" min="0" max="250" step="0.5" value="${DEFAULTS.antennaBHeightM}"></label>
      <label>GHz<input data-profile="frequency" type="number" min="0.001" max="100" step="0.1" value="${DEFAULTS.frequencyMhz / 1000}"></label>
      <label>Fresnel<select data-profile="fresnel">${[1, 2, 3, 4].map((zone) => `<option value="${zone}">F${zone}</option>`).join("")}</select></label>
      <label>Samples<select data-profile="samples">${[11, 25, 51, 101, 201].map(sampleOption).join("")}</select></label>
    </div>
    <button data-profile="calculate" type="button">Calculate profile</button>
    <svg class="leaflet-profile-chart" viewBox="0 0 520 205" role="img"></svg>
    <div class="leaflet-profile-status">Choose settings, then calculate.</div>`;
  renderPreview(div, link);
  return div;
}

function bindProfileControls(content, context, link) {
  content.addEventListener("input", () => renderPreview(content, link));
  content.addEventListener("change", () => renderPreview(content, link));
  content.querySelector('[data-profile="calculate"]').addEventListener("click", async () => {
    await calculateProfile(content, context, link);
  });
}

async function calculateProfile(content, context, link) {
  const button = content.querySelector('[data-profile="calculate"]');
  const settings = readSettings(content);
  const settingsKey = profileSettingsKey(settings);
  button.disabled = true;
  content.querySelector(".leaflet-profile-status").textContent = "Calculating sampled profile...";
  try {
    const payload = await requestProfile(context, link, settings);
    if (settingsKey !== profileSettingsKey(readSettings(content))) return;
    renderBackendProfile(content, payload, link);
  } catch (error) {
    content.querySelector(".leaflet-profile-status").textContent = `Profile calculation failed: ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

function profileSettingsKey(settings) {
  return [settings.source, antennaHeight(settings, "A"), antennaHeight(settings, "B"), settings.frequencyMhz, settings.fresnelZone, settings.sampleCount].join("|");
}

async function requestProfile(context, link, settings) {
  const response = await callFetch(context.fetchFn, `${context.apiBaseUrl}/api/v1/profile/path`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildLeafletPathProfileRequest(link, settings, context.provider())),
  });
  if (!response.ok) throw new Error(await responseErrorText(response));
  return response.json();
}

function callFetch(fetchFn, url, options) {
  return fetchFn.call(globalThis, url, options);
}

async function responseErrorText(response) {
  try {
    const payload = await response.json();
    return payload.detail || `HTTP ${response.status}`;
  } catch (_error) {
    return `HTTP ${response.status}`;
  }
}

function renderPreview(content, link) {
  const settings = readSettings(content);
  const samples = localSamples(link, settings);
  renderChart(content, samples, link);
  content.querySelector(".leaflet-profile-status").textContent = `${settings.sourceLabel} preview. Calculate profile to sample rasters.`;
}

function renderBackendProfile(content, payload, link) {
  const samples = payload.samples.map((sample) => ({
    ratio: sample.ratio,
    distance: sample.distance_m,
    los: sample.los_height_m,
    upper: sample.los_height_m + sample.fresnel_radius_m,
    lower: sample.fresnel_lower_m,
    dgm: sample.dgm_m,
    dom: sample.dom_m,
    terrain: sample.selected_height_m,
    clearance: sample.clearance_m,
    site: endpointSite(link, sample.ratio),
  }));
  renderChart(content, samples, link);
  content.querySelector(".leaflet-profile-status").textContent = backendStatus(payload.samples, payload.warnings || []);
}

function renderChart(content, samples, link) {
  const chart = content.querySelector(".leaflet-profile-chart");
  const scale = chartScale(samples);
  const dgm = finitePath(samples, scale, "dgm");
  const dom = finitePath(samples, scale, "dom");
  const terrain = dgm || dom ? "" : finitePath(samples, scale, "terrain");
  chart.innerHTML = `
    ${axisLabels(scale)}
    <path class="profile-fresnel-fill" d="${path([...samples].reverse(), scale, "upper")} L ${path(samples, scale, "lower").slice(2)} Z"></path>
    <path class="profile-fresnel-line" d="${path(samples, scale, "upper")}"></path>
    <path class="profile-fresnel-line" d="${path(samples, scale, "lower")}"></path>
    <path class="profile-link-line" d="${path(samples, scale, "los")}"></path>
    ${dgm ? `<path class="profile-dgm-line" d="${dgm}"></path>` : ""}
    ${dom ? `<path class="profile-dom-line" d="${dom}"></path>` : ""}
    ${terrain ? `<path class="profile-terrain-line" d="${terrain}"></path>` : ""}
    ${antennaPoles(samples, scale)}
    ${xAxisLabels(samples, scale)}
    ${legend(dgm, dom)}
    <rect class="profile-hitbox" x="52" y="18" width="450" height="158"></rect>
    <g class="profile-cursor" hidden><line class="profile-cursor-line" x1="52" y1="18" x2="52" y2="176"></line><text class="profile-cursor-label" x="60" y="34"></text></g>
    <text x="52" y="20">LOS / Fresnel</text><text x="52" y="192">${escapeSvg(endpointName(link.siteA, "Site A"))}</text><text text-anchor="end" x="502" y="192">${escapeSvg(endpointName(link.siteB, "Site B"))}</text>`;
  bindProfileCursor(chart, samples, scale);
}

function localSamples(link, settings) {
  const distanceM = Math.max(1, link.distanceM);
  const samples = sampleCount(settings.sampleCount);
  return Array.from({ length: samples }, (_, index) => {
    const ratio = index / (samples - 1);
    const los = losHeight(link, settings, ratio);
    const fresnel = fresnelRadius(distanceM, settings.frequencyMhz, settings.fresnelZone, ratio);
    return { ratio, distance: distanceM * ratio, los, upper: los + fresnel, lower: los - fresnel, terrain: null, site: endpointSite(link, ratio) };
  });
}

function readSettings(content) {
  const source = content.querySelector('input[name="leafletProfileSource"]:checked')?.value || DEFAULTS.source;
  return {
    source,
    sourceLabel: SOURCES.find(([value]) => value === source)?.[1] || "Profile",
    antennaAHeightM: positive(content.querySelector('[data-profile="antenna-a"]').value, DEFAULTS.antennaAHeightM),
    antennaBHeightM: positive(content.querySelector('[data-profile="antenna-b"]').value, DEFAULTS.antennaBHeightM),
    frequencyMhz: gigahertzToMegahertz(content.querySelector('[data-profile="frequency"]').value),
    fresnelZone: positive(content.querySelector('[data-profile="fresnel"]').value, DEFAULTS.fresnelZone),
    sampleCount: sampleCount(content.querySelector('[data-profile="samples"]').value),
  };
}

function linkFromSites(siteA, siteB) {
  return { label: linkLabel(siteA, siteB), siteA, siteB, distanceM: haversine(siteA, siteB) };
}

function linkFromNetwork(p) {
  return linkFromSites(
    siteFromNetwork(p, "a"),
    siteFromNetwork(p, "b"),
  );
}

function siteFromNetwork(p, side) {
  return {
    lat: p[`lat_${side}`],
    lon: p[`lon_${side}`],
    height: 0,
    name: p[`site_${side}`] || "",
    label: p[`site_label_${side}`] || "",
    id: p[`s_number_${side}`] || "",
    type: p[`site_type_${side}`] || "",
    structure: p[`site_structure_${side}`] || "",
  };
}

function linkLabel(siteA, siteB) {
  const a = endpointName(siteA, "Site A");
  const b = endpointName(siteB, "Site B");
  return `${a} to ${b}`;
}

function linkDetails(link) {
  const details = [siteDetail("A", link.siteA), siteDetail("B", link.siteB)].filter(Boolean).join("");
  return details ? `<div class="leaflet-profile-sites">${details}</div>` : "";
}

function siteDetail(side, site) {
  const identity = [site.name, site.id && `(${site.id})`].filter(Boolean).join(" ");
  const details = [site.label, site.structure, site.type].filter(Boolean).join(" - ");
  return identity || details ? `<div>${side}: ${escapeHtml(identity || "site")}${details ? ` - ${escapeHtml(details)}` : ""}</div>` : "";
}

function sourceRadio([value, label]) {
  const checked = value === DEFAULTS.source ? "checked" : "";
  return `<label><input type="radio" name="leafletProfileSource" value="${value}" ${checked}> ${label}</label>`;
}

function sampleOption(value) {
  const selected = value === DEFAULTS.sampleCount ? "selected" : "";
  return `<option value="${value}" ${selected}>${value}</option>`;
}

function chartScale(samples) {
  const values = samples.flatMap((sample) => [sample.upper, sample.lower, sample.terrain, sample.dgm, sample.dom]).filter((value) => Number.isFinite(value));
  const min = Math.min(...values) - 5;
  const max = Math.max(...values) + 5;
  return { min, max, x: (ratio) => 52 + ratio * 450, y: (value) => 18 + (max - value) / (max - min) * 142 };
}

function path(samples, scale, key) {
  return samples.map((sample, index) => `${index ? "L" : "M"} ${scale.x(sample.ratio).toFixed(1)} ${scale.y(sample[key]).toFixed(1)}`).join(" ");
}

function finitePath(samples, scale, key) {
  return path(samples.filter((sample) => Number.isFinite(sample[key])), scale, key);
}

function axisLabels(scale) {
  const ticks = [scale.max, (scale.max + scale.min) / 2, scale.min];
  return ticks.map((value) => `<text class="profile-axis-label" x="6" y="${scale.y(value).toFixed(1)}">${value.toFixed(0)} m</text>`).join("");
}

function xAxisLabels(samples, scale) {
  const totalM = samples.at(-1)?.distance || 0;
  if (!totalM) return "";
  return [0, 0.5, 1].map((ratio) => {
    const km = (totalM * ratio / 1000).toFixed(1);
    const anchor = ratio === 0 ? "start" : ratio === 1 ? "end" : "middle";
    return `<text class="profile-axis-label" text-anchor="${anchor}" x="${scale.x(ratio).toFixed(1)}" y="176">${km} km</text>`;
  }).join("");
}

function antennaPoles(samples, scale) {
  return [firstFiniteTerrain(samples), lastFiniteTerrain(samples)].filter(Boolean).map((sample) => {
    const x = scale.x(sample.ratio).toFixed(1);
    const groundY = scale.y(sample.terrain).toFixed(1);
    const antennaY = scale.y(sample.los).toFixed(1);
    return `<path class="profile-antenna-pole" d="M ${x} ${groundY} L ${x} ${antennaY}"></path><circle class="profile-antenna-dot" cx="${x}" cy="${antennaY}" r="3"></circle>`;
  }).join("");
}

function firstFiniteTerrain(samples) {
  return samples.find((sample) => Number.isFinite(sample.terrain));
}

function lastFiniteTerrain(samples) {
  return [...samples].reverse().find((sample) => Number.isFinite(sample.terrain));
}

function legend(dgm, dom) {
  const dgmText = dgm ? '<text class="profile-legend-dgm" x="340" y="20">DGM</text>' : "";
  const domText = dom ? '<text class="profile-legend-dom" x="390" y="20">DOM</text>' : "";
  return dgmText + domText;
}

function bindProfileCursor(chart, samples, scale) {
  const hitbox = chart.querySelector(".profile-hitbox");
  const cursor = chart.querySelector(".profile-cursor");
  if (!hitbox || !cursor || !samples.length) return;
  hitbox.addEventListener("pointermove", (event) => updateCursor(chart, cursor, samples, scale, event));
  hitbox.addEventListener("pointerdown", (event) => updateCursor(chart, cursor, samples, scale, event));
  hitbox.addEventListener("pointerleave", () => cursor.setAttribute("hidden", ""));
}

function updateCursor(chart, cursor, samples, scale, event) {
  const sample = nearestSample(samples, pointerRatio(chart, event));
  const x = scale.x(sample.ratio);
  cursor.removeAttribute("hidden");
  cursor.querySelector("line").setAttribute("x1", x.toFixed(1));
  cursor.querySelector("line").setAttribute("x2", x.toFixed(1));
  const label = cursor.querySelector("text");
  const rightSide = x > 330;
  label.setAttribute("text-anchor", rightSide ? "end" : "start");
  label.setAttribute("x", (rightSide ? x - 8 : x + 8).toFixed(1));
  label.textContent = cursorLabel(sample);
}

function pointerRatio(chart, event) {
  const box = chart.getBoundingClientRect();
  const viewX = (event.clientX - box.left) / box.width * 520;
  return Math.max(0, Math.min(1, (viewX - 52) / 450));
}

function nearestSample(samples, ratio) {
  return samples.reduce((best, sample) => Math.abs(sample.ratio - ratio) < Math.abs(best.ratio - ratio) ? sample : best, samples[0]);
}

function cursorLabel(sample) {
  const parts = [`${distanceValue(sample.distance)}`];
  if (Number.isFinite(sample.dgm)) parts.push(`DGM ${sample.dgm.toFixed(1)} m`);
  if (Number.isFinite(sample.dom)) parts.push(`DOM ${sample.dom.toFixed(1)} m`);
  if (Number.isFinite(sample.terrain) && !Number.isFinite(sample.dgm) && !Number.isFinite(sample.dom)) parts.push(`H ${sample.terrain.toFixed(1)} m`);
  if (Number.isFinite(sample.los)) parts.push(`LOS ${sample.los.toFixed(1)} m`);
  if (Number.isFinite(sample.clearance)) parts.push(`Clr ${sample.clearance.toFixed(1)} m`);
  return parts.join(" | ");
}

function backendStatus(samples, warnings) {
  const clearances = samples.map((sample) => sample.clearance_m).filter((value) => Number.isFinite(value));
  const clearance = clearances.length ? `${Math.min(...clearances).toFixed(1)} m` : "unavailable";
  return `Sampled raster profile (${samples.length} samples). Minimum clearance: ${clearance}.${warnings.length ? ` Warnings: ${warnings.length}` : ""}`;
}

function losHeight(link, settings, ratio) {
  const startM = endpoint(link.siteA).height_m + antennaHeight(settings, "A");
  const endM = endpoint(link.siteB).height_m + antennaHeight(settings, "B");
  return startM + (endM - startM) * ratio;
}

function antennaHeight(settings, side) {
  const value = settings[`antenna${side}HeightM`] ?? settings.antennaHeightM ?? DEFAULTS[`antenna${side}HeightM`];
  return positive(value, DEFAULTS[`antenna${side}HeightM`]);
}

function fresnelRadius(distanceM, frequencyMhz, zone, ratio) {
  const wavelength = 299792458 / (frequencyMhz * 1_000_000);
  return Math.sqrt((Math.max(1, zone) * wavelength * distanceM * ratio * distanceM * (1 - ratio)) / distanceM);
}

function midpoint(link) {
  return [(link.siteA.lat + link.siteB.lat) / 2, (link.siteA.lon + link.siteB.lon) / 2];
}

function insideBbox([lat, lon], bbox) {
  return bbox.west <= lon && lon <= bbox.east && bbox.south <= lat && lat <= bbox.north;
}

function distanceLabel(link) {
  return link.distanceM >= 1000 ? `${(link.distanceM / 1000).toFixed(2)} km` : `${link.distanceM.toFixed(0)} m`;
}

function distanceValue(distanceM) {
  return distanceM >= 1000 ? `${(distanceM / 1000).toFixed(2)} km` : `${distanceM.toFixed(0)} m`;
}

function haversine(siteA, siteB) {
  const radiusM = 6371000;
  const dLat = (siteB.lat - siteA.lat) * Math.PI / 180;
  const dLon = (siteB.lon - siteA.lon) * Math.PI / 180;
  const aLat = siteA.lat * Math.PI / 180;
  const bLat = siteB.lat * Math.PI / 180;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(aLat) * Math.cos(bLat) * Math.sin(dLon / 2) ** 2;
  return 2 * radiusM * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}

function endpoint(site) {
  return { lon: site.lon, lat: site.lat, height_m: Number.isFinite(site.height) ? site.height : 0 };
}

function endpointSite(link, ratio) {
  if (ratio <= 0.000001) return link.siteA;
  if (ratio >= 0.999999) return link.siteB;
  return null;
}

function endpointName(site, fallback) {
  return site?.name || site?.label || site?.id || fallback;
}

function positive(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : fallback;
}

export function gigahertzToMegahertz(value) {
  return positive(value, DEFAULTS.frequencyMhz / 1000) * 1000;
}

function sampleCount(value) {
  const count = Math.round(positive(value, DEFAULTS.sampleCount));
  return Math.max(3, Math.min(201, count));
}

function escapeHtml(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function escapeSvg(value) {
  return escapeHtml(value);
}
