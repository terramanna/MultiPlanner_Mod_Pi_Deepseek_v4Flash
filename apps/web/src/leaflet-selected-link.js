export function openSelectedLinkPopup(context, event) {
  const { L, map, linkProfile, onCorridor, selectedLink, siteA, siteB } = context;
  const popup = popupContent(selectedLink, siteA, siteB);
  popup.querySelector('[data-action="profile"]').addEventListener("click", () => {
    map.closePopup();
    linkProfile.openSites(siteA, siteB, event.latlng);
  });
  popup.querySelector('[data-action="corridor"]').addEventListener("click", () => {
    map.closePopup();
    onCorridor();
  });
  L.popup({ maxWidth: 380 }).setLatLng(event.latlng).setContent(popup).openOn(map);
}

export function selectedLinkDetails(link, siteA, siteB) {
  const details = linkDetails(link, siteA, siteB);
  return [
    details.name,
    `${distanceLabel(details.distanceM)} A to B`,
    siteLine("A", details.siteA),
    siteLine("B", details.siteB),
  ].filter(Boolean);
}

function linkDetails(link, siteA, siteB) {
  const value = link || {};
  return {
    distanceM: value.distance_m || haversine(siteA, siteB),
    name: value.link_name || "Selected Site A to Site B",
    siteA: [value.site_a_name, value.site_a_id, value.site_a_label, value.site_a_structure, value.site_a_type],
    siteB: [value.site_b_name, value.site_b_id, value.site_b_label, value.site_b_structure, value.site_b_type],
  };
}

function popupContent(link, siteA, siteB) {
  const div = document.createElement("div");
  div.className = "selected-link-popup";
  div.innerHTML = `
    ${selectedLinkDetails(link, siteA, siteB).map((line, index) => detailLine(line, index)).join("")}
    <div class="net-popup-actions">
      <button type="button" data-action="corridor">Corridor</button>
      <button type="button" data-action="profile">Profile</button>
    </div>`;
  return div;
}

function detailLine(line, index) {
  return index === 0 ? `<strong>${escapeHtml(line)}</strong>` : `<br/><small>${escapeHtml(line)}</small>`;
}

function siteLine(side, [name, id, label, structure, type]) {
  const site = [name, id && `(${id})`].filter(Boolean).join(" ");
  const details = [label, structure, type].filter(Boolean).join(" · ");
  return `${side}: ${site || "site"}${details ? ` - ${details}` : ""}`;
}

function distanceLabel(distanceM) {
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

function escapeHtml(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}
