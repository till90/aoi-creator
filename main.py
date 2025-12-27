#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AOI Studio – AOI zeichnen & exportieren (GeoJSON / WKT / EWKT / KML)

Ziel:
- Zeichnen: Polygon & Rechteck (Leaflet + Leaflet.Draw)
- Editieren/Löschen: aktiv
- Mehrere Features erlaubt
- Export:
  - GeoJSON (FeatureCollection) im gewählten CRS (Default: EPSG:4326)
  - WKT / EWKT im gewählten CRS
  - KML immer EPSG:4326 (WGS84)
- CRS:
  - EPSG:4326
  - AUTO_UTM (25832/25833 nach AOI-Zentrum)
  - EPSG:25832 / EPSG:25833
  - EPSG:3857

Hinweis:
- Alles passiert clientseitig. Server speichert nichts.
- Für Cloud Run geeignet (PORT env).
"""

import os
from flask import Flask, Response, jsonify, render_template_string

APP_TITLE = os.getenv("APP_TITLE", "AOI Studio – Zeichnen & Export")
START_LAT = float(os.getenv("START_LAT", "49.8728"))   # Darmstadt default
START_LON = float(os.getenv("START_LON", "8.6512"))
START_ZOOM = int(os.getenv("START_ZOOM", "12"))

INDEX_HTML = r"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="theme-color" content="#0b1020" />
  <title>{{ title }}</title>

  <link rel="preconnect" href="https://unpkg.com" crossorigin>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css" />
  <link rel="stylesheet" href="/static/app.css" />
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <div class="dot" aria-hidden="true"></div>
      <div class="titles">
        <div class="title">{{ title }}</div>
        <div class="subtitle">
          Polygon/Rechteck zeichnen · Edit/Delete · Export: GeoJSON/WKT/EWKT/KML
        </div>
      </div>
    </div>

    <div class="topbar-right">
      <a class="chip" href="/api/healthz" target="_blank" rel="noopener">/api/healthz</a>
      <a class="chip" href="/api/example" target="_blank" rel="noopener">/api/example</a>
    </div>
  </header>

  <main class="layout">
    <section class="map-card" aria-label="Karte">
      <div id="map"></div>
      <div class="map-hint">
        Tipp: Zeichnen links oben · AOI anklicken → editierbar · “Alles löschen” räumt komplett auf
      </div>
    </section>

    <aside class="panel" aria-label="Export & Ausgabe">
      <div id="toast" class="toast" role="status" aria-live="polite" aria-atomic="true" hidden></div>

      <div class="panel-card">
        <div class="panel-head">
          <div class="panel-title">AOI</div>
          <div id="meta" class="panel-meta">Noch keine AOI</div>
        </div>

        <div class="btn-row">
          <button id="btn-fit" class="btn" disabled>Auf AOI zoomen</button>
          <button id="btn-clear" class="btn btn-ghost">Alles löschen</button>
        </div>

        <div id="status" class="status" data-kind="idle">
          Zeichne ein Polygon oder Rechteck, dann erscheinen Export & Copy/Download.
        </div>
      </div>

      <div class="panel-card">
        <div class="panel-head">
          <div class="panel-title">Export-Einstellungen</div>
          <div class="panel-meta">CRS & Format</div>
        </div>

        <div class="field">
          <label for="sel-crs">Export CRS</label>
          <select id="sel-crs">
            <option value="EPSG:4326" selected>WGS84 (EPSG:4326) – Standard</option>
            <option value="AUTO_UTM">Auto UTM (Zone nach AOI-Zentrum)</option>
            <option value="EPSG:25832">UTM 32N (EPSG:25832) – oft Hessen</option>
            <option value="EPSG:25833">UTM 33N (EPSG:25833)</option>
            <option value="EPSG:3857">Web Mercator (EPSG:3857)</option>
          </select>
          <div class="help">
            Hinweis: GeoJSON ist standardmäßig EPSG:4326. Andere CRS können in manchen Tools als “nicht RFC 7946-konform” gelten.
          </div>
        </div>

        <div class="field">
          <label for="sel-format">Zusatzformat</label>
          <select id="sel-format">
            <option value="WKT" selected>WKT</option>
            <option value="EWKT">EWKT (SRID=…;WKT)</option>
            <option value="KML">KML (immer EPSG:4326)</option>
          </select>
        </div>
      </div>

      <div class="panel-card">
        <div class="tabs" role="tablist" aria-label="Ausgabe wählen">
          <button id="tab-geo" class="tab is-active" role="tab" aria-selected="true" aria-controls="pane-geo">GeoJSON</button>
          <button id="tab-alt" class="tab" role="tab" aria-selected="false" aria-controls="pane-alt">WKT/KML</button>
        </div>

        <section id="pane-geo" class="pane is-active" role="tabpanel" aria-labelledby="tab-geo">
          <div class="pane-head">
            <div id="lbl-geo" class="pane-title">GeoJSON</div>
            <div class="pane-actions">
              <button id="btn-geo-dl" class="btn btn-primary" disabled>Download</button>
              <button id="btn-geo-copy" class="btn" disabled>Kopieren</button>
            </div>
          </div>
          <textarea id="out-geo" spellcheck="false" placeholder="Hier erscheint das GeoJSON …"></textarea>
        </section>

        <section id="pane-alt" class="pane" role="tabpanel" aria-labelledby="tab-alt">
          <div class="pane-head">
            <div id="lbl-alt" class="pane-title">WKT</div>
            <div class="pane-actions">
              <button id="btn-alt-dl" class="btn btn-primary" disabled>Download</button>
              <button id="btn-alt-copy" class="btn" disabled>Kopieren</button>
            </div>
          </div>
          <textarea id="out-alt" spellcheck="false" placeholder="Hier erscheint WKT/EWKT/KML …"></textarea>
        </section>
      </div>

      <div class="panel-foot">
        Basemaps: OSM & ESRI · Zeichnen & Export komplett im Browser · Server speichert nichts
      </div>
    </aside>
  </main>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.js"></script>
  <script src="https://unpkg.com/proj4@2.9.2/dist/proj4.js"></script>

  <script>
    window.__AOI_STUDIO__ = {
      startLat: {{ start_lat }},
      startLon: {{ start_lon }},
      startZoom: {{ start_zoom }},
      title: {{ title|tojson }}
    };
  </script>
  <script src="/static/app.js"></script>
</body>
</html>
"""

APP_CSS = r"""
:root{
  --bg: #f6f7fb;
  --card: #ffffff;
  --text: #0f172a;
  --muted: #55607a;
  --border: rgba(15,23,42,.10);
  --shadow: 0 10px 30px rgba(15,23,42,.08);
  --primary: #2563eb;
  --primary-weak: rgba(37,99,235,.12);
  --danger: #dc2626;
  --ok: #16a34a;
  --radius: 16px;
  --radius-sm: 12px;
  --font: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
  --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  --container: 1280px;
  --gap: 14px;
}

@media (prefers-color-scheme: dark){
  :root{
    --bg: #0b1020;
    --card: #101a33;
    --text: #e8eefc;
    --muted: #aab6d6;
    --border: rgba(255,255,255,.10);
    --shadow: 0 18px 60px rgba(0,0,0,.35);
    --primary: #6ea8fe;
    --primary-weak: rgba(110,168,254,.16);
  }
}

*{ box-sizing: border-box; }
html, body{ height: 100%; }
body{
  margin: 0;
  font-family: var(--font);
  color: var(--text);
  background: var(--bg);
}

.topbar{
  max-width: var(--container);
  margin: 14px auto 0;
  padding: 0 14px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap: 12px;
}

.brand{ display:flex; align-items:center; gap: 12px; min-width: 0; }
.dot{
  width: 12px; height: 12px; border-radius: 999px;
  background: var(--primary);
  box-shadow: 0 0 0 6px var(--primary-weak);
  flex: 0 0 auto;
}
.titles{ min-width: 0; }
.title{
  font-weight: 750;
  letter-spacing: .2px;
  font-size: 15px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.subtitle{
  margin-top: 2px;
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.topbar-right{
  display:flex; gap: 8px; align-items:center; flex: 0 0 auto;
}
.chip{
  display:inline-flex;
  align-items:center;
  padding: 8px 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  color: var(--muted);
  text-decoration:none;
  font-size: 12px;
  background: rgba(255,255,255,.6);
}
@media (prefers-color-scheme: dark){
  .chip{ background: rgba(255,255,255,.06); }
}
.chip:hover{ color: var(--text); border-color: rgba(37,99,235,.35); }

.layout{
  max-width: var(--container);
  margin: 12px auto 18px;
  padding: 0 14px 20px;
  display:grid;
  grid-template-columns: 1.2fr .8fr;
  gap: var(--gap);
  align-items:start;
}

.map-card, .panel-card{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow:hidden;
}

#map{ height: 72vh; min-height: 520px; width: 100%; }
.map-hint{
  padding: 10px 12px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--muted);
  background: rgba(255,255,255,.4);
}
@media (prefers-color-scheme: dark){
  .map-hint{ background: rgba(0,0,0,.18); }
}

.panel{ display:flex; flex-direction:column; gap: var(--gap); position: sticky; top: 12px; }
.panel-card{ padding: 12px; }

.panel-head{
  display:flex;
  align-items:baseline;
  justify-content:space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.panel-title{ font-weight: 750; font-size: 13px; letter-spacing: .2px; }
.panel-meta{ font-size: 12px; color: var(--muted); white-space: nowrap; }

.btn-row{ display:flex; gap: 10px; flex-wrap:wrap; }

.btn{
  appearance:none;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.7);
  color: var(--text);
  padding: 10px 12px;
  border-radius: 12px;
  cursor:pointer;
  font-weight: 650;
  font-size: 13px;
}
@media (prefers-color-scheme: dark){
  .btn{ background: rgba(255,255,255,.06); }
}
.btn:hover{ border-color: rgba(37,99,235,.35); }
.btn:disabled{ opacity:.55; cursor:not-allowed; }

.btn-primary{
  border-color: rgba(37,99,235,.35);
  background: var(--primary-weak);
}
.btn-ghost{
  border-color: rgba(220,38,38,.25);
  background: rgba(220,38,38,.06);
}
.btn-ghost:hover{ border-color: rgba(220,38,38,.45); }

.status{
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.5);
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.35;
}
@media (prefers-color-scheme: dark){
  .status{ background: rgba(0,0,0,.18); }
}
.status[data-kind="ok"]{
  border-color: rgba(22,163,74,.35);
  background: rgba(22,163,74,.08);
  color: var(--text);
}
.status[data-kind="err"]{
  border-color: rgba(220,38,38,.35);
  background: rgba(220,38,38,.10);
  color: var(--text);
}

.field{ display:flex; flex-direction:column; gap: 6px; margin-top: 10px; }
label{ font-size: 12px; color: var(--muted); }

select{
  appearance:none;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.7);
  color: var(--text);
  padding: 10px 12px;
  border-radius: 12px;
  font-weight: 650;
  cursor: pointer;
  outline: none;
}
@media (prefers-color-scheme: dark){
  select{ background: rgba(255,255,255,.06); }
}
select:focus{
  border-color: rgba(37,99,235,.55);
  box-shadow: 0 0 0 4px var(--primary-weak);
}

.help{
  font-size: 12px;
  color: var(--muted);
  line-height: 1.35;
}

.tabs{
  display:flex;
  gap: 8px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 10px;
  margin-bottom: 10px;
}
.tab{
  appearance:none;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.7);
  color: var(--muted);
  padding: 8px 10px;
  border-radius: 999px;
  font-weight: 700;
  cursor:pointer;
  font-size: 12px;
}
@media (prefers-color-scheme: dark){
  .tab{ background: rgba(255,255,255,.06); }
}
.tab.is-active{
  color: var(--text);
  border-color: rgba(37,99,235,.35);
  background: var(--primary-weak);
}

.pane{ display:none; }
.pane.is-active{ display:block; }

.pane-head{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.pane-title{ font-weight: 750; font-size: 12px; color: var(--muted); }
.pane-actions{ display:flex; gap: 8px; flex-wrap:wrap; }

textarea{
  width:100%;
  min-height: 240px;
  resize: vertical;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.7);
  border-radius: 12px;
  padding: 10px 12px;
  font-family: var(--mono);
  font-size: 12px;
  color: var(--text);
  outline:none;
}
@media (prefers-color-scheme: dark){
  textarea{ background: rgba(255,255,255,.04); }
}
textarea:focus{
  border-color: rgba(37,99,235,.55);
  box-shadow: 0 0 0 4px var(--primary-weak);
}

.panel-foot{
  font-size: 12px;
  color: var(--muted);
  padding: 2px 2px 0;
}

/* Toast */
.toast{
  position: sticky;
  top: 0;
  z-index: 5;
  margin-bottom: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.85);
  color: var(--text);
  box-shadow: var(--shadow);
}
@media (prefers-color-scheme: dark){
  .toast{ background: rgba(16,26,51,.92); }
}

/* Leaflet Controls - unify look */
.leaflet-control-layers,
.leaflet-bar{
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  overflow: hidden;
  box-shadow: var(--shadow);
}
.leaflet-control-layers{
  background: var(--card) !important;
  color: var(--text) !important;
}

/* Leaflet.Draw sprite fix (CDN images) */
.leaflet-draw-toolbar a{
  background-image: url("https://unpkg.com/leaflet-draw@1.0.4/dist/images/spritesheet.png") !important;
  background-repeat: no-repeat;
}
.leaflet-retina .leaflet-draw-toolbar a{
  background-image: url("https://unpkg.com/leaflet-draw@1.0.4/dist/images/spritesheet-2x.png") !important;
  background-size: 300px 30px;
}

/* Responsive */
@media (max-width: 980px){
  .layout{ grid-template-columns: 1fr; }
  .panel{ position: static; }
  #map{ height: 58vh; min-height: 420px; }
}
"""

APP_JS = r"""
(() => {
  const CFG = window.__AOI_STUDIO__ || { startLat: 49.8728, startLon: 8.6512, startZoom: 12 };

  // ---- DOM
  const $ = (id) => document.getElementById(id);

  const elMeta = $("meta");
  const elStatus = $("status");
  const elToast = $("toast");

  const btnFit = $("btn-fit");
  const btnClear = $("btn-clear");

  const selCrs = $("sel-crs");
  const selFormat = $("sel-format");

  const tabGeo = $("tab-geo");
  const tabAlt = $("tab-alt");
  const paneGeo = $("pane-geo");
  const paneAlt = $("pane-alt");

  const lblGeo = $("lbl-geo");
  const lblAlt = $("lbl-alt");

  const outGeo = $("out-geo");
  const outAlt = $("out-alt");

  const btnGeoDl = $("btn-geo-dl");
  const btnGeoCopy = $("btn-geo-copy");
  const btnAltDl = $("btn-alt-dl");
  const btnAltCopy = $("btn-alt-copy");

  // ---- Toast
  let toastTimer = null;
  function toast(msg) {
    if (!elToast) return;
    elToast.textContent = msg;
    elToast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { elToast.hidden = true; }, 2200);
  }

  function setStatus(kind, html) {
    elStatus.dataset.kind = kind || "idle";
    elStatus.innerHTML = html;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
    }[c]));
  }

  function safeStringify(obj) {
    try { return JSON.stringify(obj, null, 2); } catch { return ""; }
  }

  // ---- Proj4 defs
  try {
    proj4.defs("EPSG:25832", "+proj=utm +zone=32 +ellps=GRS80 +units=m +no_defs +type=crs");
    proj4.defs("EPSG:25833", "+proj=utm +zone=33 +ellps=GRS80 +units=m +no_defs +type=crs");
  } catch {}

  // ---- Map
  const map = L.map("map", { preferCanvas: true }).setView([CFG.startLat, CFG.startLon], CFG.startZoom);

  const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 20,
    attribution: "&copy; OpenStreetMap"
  });

  const esriSat = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 20, attribution: "Tiles &copy; Esri" }
  );

  const esriRef = L.tileLayer(
    "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 20, attribution: "Labels &copy; Esri" }
  );

  osm.addTo(map);
  L.control.layers({ "OSM": osm, "Satellit": esriSat }, { "Satellit Labels": esriRef }, { collapsed: true }).addTo(map);

  // ---- Draw
  const drawn = new L.FeatureGroup().addTo(map);
  const drawControl = new L.Control.Draw({
    position: "topleft",
    draw: {
      polyline: false,
      circle: false,
      circlemarker: false,
      marker: false,
      polygon: { allowIntersection: false, showArea: true },
      rectangle: true
    },
    edit: { featureGroup: drawn, edit: true, remove: true }
  });
  map.addControl(drawControl);

  // ---- AOI helpers
  function buildFC4326() {
    const fc = { type: "FeatureCollection", features: [] };
    for (const layer of drawn.getLayers()) {
      const f = layer.toGeoJSON();
      if (!f || f.type !== "Feature") continue;
      f.properties = Object.assign({}, f.properties || {}, { epsg: 4326 });
      fc.features.push(f);
    }
    return fc;
  }

  function getCenterInfo() {
    const layers = drawn.getLayers();
    if (!layers.length) return null;
    const b = drawn.getBounds();
    if (!b || !b.isValid()) return null;
    const c = b.getCenter();
    return { lon: c.lng, lat: c.lat, bounds: b };
  }

  function pickAutoUtm(lon) {
    return (lon < 12.0) ? "EPSG:25832" : "EPSG:25833";
  }

  function roundPair(xy, epsg) {
    const [x, y, z] = xy;
    const is4326 = (epsg === "EPSG:4326");
    const dx = is4326 ? +x.toFixed(6) : +x.toFixed(2);
    const dy = is4326 ? +y.toFixed(6) : +y.toFixed(2);
    return (typeof z === "number") ? [dx, dy, z] : [dx, dy];
  }

  function transformCoords(coords, fromCrs, toCrs, epsgOut) {
    if (!coords) return coords;
    if (typeof coords[0] === "number") {
      const x = coords[0], y = coords[1];
      const z = (coords.length > 2) ? coords[2] : undefined;
      const out = proj4(fromCrs, toCrs, [x, y]);
      return roundPair((typeof z === "number") ? [out[0], out[1], z] : [out[0], out[1]], epsgOut);
    }
    return coords.map(c => transformCoords(c, fromCrs, toCrs, epsgOut));
  }

  function transformFC(fc4326, epsgOut) {
    if (epsgOut === "EPSG:4326") {
      const out = JSON.parse(JSON.stringify(fc4326));
      for (const f of out.features) f.properties = Object.assign({}, f.properties || {}, { epsg: 4326 });
      return out;
    }
    const fromCrs = "EPSG:4326";
    const toCrs = epsgOut;
    // sanity check
    proj4(fromCrs, toCrs, [0, 0]);

    const out = JSON.parse(JSON.stringify(fc4326));
    for (const f of out.features) {
      if (!f.geometry || !f.geometry.coordinates) continue;
      f.geometry.coordinates = transformCoords(f.geometry.coordinates, fromCrs, toCrs, epsgOut);
      f.properties = Object.assign({}, f.properties || {}, {
        epsg: parseInt(epsgOut.split(":")[1], 10),
        source_epsg: 4326
      });
    }
    return out;
  }

  // ---- WKT / EWKT / KML
  function ensureClosed(ring) {
    if (!ring || ring.length < 3) return ring;
    const a = ring[0], b = ring[ring.length - 1];
    if (a[0] === b[0] && a[1] === b[1]) return ring;
    return ring.concat([[a[0], a[1]]]);
  }

  function ringToWkt(ring) {
    const rr = ensureClosed(ring);
    return rr.map(pt => `${pt[0]} ${pt[1]}`).join(", ");
  }

  function polygonToWkt(polyCoords) {
    // polyCoords: [ outerRing, hole1, ... ]
    const rings = (polyCoords || []).map(r => `(${ringToWkt(r)})`).join(", ");
    return `POLYGON(${rings})`;
  }

  function multiPolygonToWkt(multiCoords) {
    // multiCoords: [ poly1, poly2, ... ] where poly = [rings...]
    const polys = (multiCoords || []).map(poly => {
      const rings = (poly || []).map(r => `(${ringToWkt(r)})`).join(", ");
      return `(${rings})`;
    }).join(", ");
    return `MULTIPOLYGON(${polys})`;
  }

  function fcToWkt(fc) {
    // merge multiple Polygon features into MULTIPOLYGON; flatten MultiPolygon features
    const polys = [];
    for (const f of (fc.features || [])) {
      const g = f.geometry;
      if (!g) continue;
      if (g.type === "Polygon") polys.push(g.coordinates);
      if (g.type === "MultiPolygon") {
        for (const poly of (g.coordinates || [])) polys.push(poly);
      }
    }
    if (!polys.length) return "";
    if (polys.length === 1) return polygonToWkt(polys[0]);
    return multiPolygonToWkt(polys);
  }

  function fc4326ToKml(fc4326) {
    // KML wants lon,lat[,alt] in WGS84
    const esc = (s) => String(s)
      .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
      .replace(/"/g,"&quot;").replace(/'/g,"&apos;");

    function ringToKml(ring) {
      const rr = ensureClosed(ring);
      return rr.map(pt => `${pt[0]},${pt[1]},0`).join(" ");
    }

    function polyToKml(poly) {
      const outer = poly && poly[0] ? poly[0] : null;
      const holes = (poly || []).slice(1);
      if (!outer) return "";
      let k = `<Polygon><outerBoundaryIs><LinearRing><coordinates>${ringToKml(outer)}</coordinates></LinearRing></outerBoundaryIs>`;
      for (const h of holes) {
        k += `<innerBoundaryIs><LinearRing><coordinates>${ringToKml(h)}</coordinates></LinearRing></innerBoundaryIs>`;
      }
      k += `</Polygon>`;
      return k;
    }

    let placemarks = "";
    let i = 1;

    for (const f of (fc4326.features || [])) {
      const g = f.geometry;
      if (!g) continue;

      let geom = "";
      if (g.type === "Polygon") geom = polyToKml(g.coordinates);
      else if (g.type === "MultiPolygon") {
        const parts = (g.coordinates || []).map(poly => polyToKml(poly)).join("");
        geom = `<MultiGeometry>${parts}</MultiGeometry>`;
      } else continue;

      const name = (f.properties && (f.properties.name || f.properties.title)) ? String(f.properties.name || f.properties.title) : `AOI ${i}`;
      placemarks += `<Placemark><name>${esc(name)}</name>${geom}</Placemark>`;
      i += 1;
    }

    return `<?xml version="1.0" encoding="UTF-8"?>` +
      `<kml xmlns="http://www.opengis.net/kml/2.2"><Document>` +
      `<name>${esc("aoi-studio export")}</name>` +
      placemarks +
      `</Document></kml>`;
  }

  // ---- Tabs
  function setTab(which) {
    const geo = (which === "geo");
    tabGeo.classList.toggle("is-active", geo);
    tabAlt.classList.toggle("is-active", !geo);
    tabGeo.setAttribute("aria-selected", String(geo));
    tabAlt.setAttribute("aria-selected", String(!geo));
    paneGeo.classList.toggle("is-active", geo);
    paneAlt.classList.toggle("is-active", !geo);
  }
  tabGeo.addEventListener("click", () => setTab("geo"));
  tabAlt.addEventListener("click", () => setTab("alt"));

  // ---- Download helper
  function downloadText(filename, text, mime) {
    const blob = new Blob([text], { type: mime || "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function zoomToAOI() {
    const b = drawn.getBounds();
    if (b && b.isValid()) map.fitBounds(b.pad(0.15));
  }

  function clearAll() {
    drawn.clearLayers();
    updateAll();
    toast("Alles gelöscht.");
  }

  // ---- Main state
  let currentFc4326 = null;
  let currentFcExport = null;
  let currentExportEpsg = "EPSG:4326";

  function resolveExportEpsg() {
    const fc4326 = buildFC4326();
    const center = getCenterInfo();
    const sel = selCrs.value;
    let epsgUsed = sel;
    if (sel === "AUTO_UTM") epsgUsed = center ? pickAutoUtm(center.lon) : "EPSG:25832";
    return { fc4326, center, sel, epsgUsed };
  }

  function updateMeta(fcCount, epsgUsed, center) {
    if (!fcCount) {
      elMeta.textContent = "Noch keine AOI";
      return;
    }
    const c = center ? `${center.lat.toFixed(5)}, ${center.lon.toFixed(5)}` : "–";
    elMeta.textContent = `${fcCount} Feature${fcCount === 1 ? "" : "s"} · Export ${epsgUsed} · Zentrum ${c}`;
  }

  function updateAltOutput() {
    const n = currentFc4326?.features?.length || 0;
    if (!n) {
      outAlt.value = "";
      lblAlt.textContent = "WKT";
      btnAltDl.disabled = true;
      btnAltCopy.disabled = true;
      return;
    }

    const fmt = selFormat.value;

    if (fmt === "KML") {
      outAlt.value = fc4326ToKml(currentFc4326);
      lblAlt.textContent = "KML (immer EPSG:4326)";
      btnAltDl.disabled = false;
      btnAltCopy.disabled = false;
      return;
    }

    const wkt = fcToWkt(currentFcExport || currentFc4326);
    if (!wkt) {
      outAlt.value = "";
      lblAlt.textContent = "WKT/EWKT (nicht verfügbar)";
      btnAltDl.disabled = true;
      btnAltCopy.disabled = true;
      return;
    }

    if (fmt === "EWKT") {
      const srid = (currentExportEpsg.split(":")[1] || "4326");
      outAlt.value = `SRID=${srid};${wkt}`;
      lblAlt.textContent = `EWKT (SRID=${srid}) – Export ${currentExportEpsg}`;
    } else {
      outAlt.value = wkt;
      lblAlt.textContent = `WKT – Export ${currentExportEpsg}`;
    }

    btnAltDl.disabled = false;
    btnAltCopy.disabled = false;
  }

  function updateAll() {
    const { fc4326, center, sel, epsgUsed } = resolveExportEpsg();
    const n = fc4326.features.length;

    currentFc4326 = fc4326;

    if (!n) {
      currentFcExport = null;
      currentExportEpsg = "EPSG:4326";
      outGeo.value = "";
      outAlt.value = "";
      lblGeo.textContent = "GeoJSON";
      lblAlt.textContent = "WKT";

      btnFit.disabled = true;
      btnGeoDl.disabled = true;
      btnGeoCopy.disabled = true;
      btnAltDl.disabled = true;
      btnAltCopy.disabled = true;

      updateMeta(0, "EPSG:4326", null);
      setStatus("idle", "Zeichne ein Polygon oder Rechteck, dann erscheinen Export & Copy/Download.");
      return;
    }

    let fcOut = null;
    let used = epsgUsed;

    try {
      fcOut = transformFC(fc4326, used);
    } catch (e) {
      fcOut = fc4326;
      used = "EPSG:4326";
      setStatus("err", `CRS-Transformation fehlgeschlagen. Fallback auf <b>EPSG:4326</b>. <span style="opacity:.9">(${escapeHtml(e?.message || String(e))})</span>`);
    }

    currentFcExport = fcOut;
    currentExportEpsg = used;

    outGeo.value = safeStringify(fcOut);
    lblGeo.textContent = `GeoJSON (Export ${used})`;

    btnFit.disabled = false;
    btnGeoDl.disabled = false;
    btnGeoCopy.disabled = false;

    updateAltOutput();

    const selLabel = (sel === "AUTO_UTM") ? `Auto UTM → <b>${escapeHtml(used)}</b>` : `<b>${escapeHtml(used)}</b>`;
    const centerLine = center ? `Zentrum: <b>${center.lat.toFixed(5)}, ${center.lon.toFixed(5)}</b>` : "";
    if (elStatus.dataset.kind !== "err") {
      setStatus("ok", `AOI gesetzt: <b>${n}</b> Feature${n===1?"":"s"} · Export: ${selLabel}${centerLine ? " · " + centerLine : ""}`);
    }
    updateMeta(n, used, center);
  }

  // ---- Events (Leaflet.Draw)
  map.on(L.Draw.Event.CREATED, (e) => {
    drawn.addLayer(e.layer);
    updateAll();
    toast("AOI hinzugefügt.");
  });

  map.on("draw:edited", () => { updateAll(); toast("AOI aktualisiert."); });
  map.on("draw:deleted", () => { updateAll(); toast("AOI gelöscht."); });

  // ---- Buttons
  btnFit.addEventListener("click", zoomToAOI);
  btnClear.addEventListener("click", clearAll);

  selCrs.addEventListener("change", () => { updateAll(); toast("Export CRS geändert."); });
  selFormat.addEventListener("change", () => { updateAltOutput(); toast("Format geändert."); });

  btnGeoDl.addEventListener("click", () => {
    const txt = outGeo.value || "";
    if (!txt.trim()) return;
    const code = (currentExportEpsg.split(":")[1] || "4326");
    downloadText(`aoi_epsg${code}.geojson`, txt, "application/geo+json;charset=utf-8");
    toast("GeoJSON Download gestartet.");
  });

  btnGeoCopy.addEventListener("click", async () => {
    const txt = outGeo.value || "";
    if (!txt.trim()) return;
    try {
      await navigator.clipboard.writeText(txt);
      toast("GeoJSON kopiert.");
    } catch {
      toast("Kopieren fehlgeschlagen (Browser-Rechte).");
    }
  });

  btnAltDl.addEventListener("click", () => {
    const txt = outAlt.value || "";
    if (!txt.trim()) return;

    const fmt = selFormat.value;
    const code = (currentExportEpsg.split(":")[1] || "4326");

    if (fmt === "KML") downloadText("aoi.kml", txt, "application/vnd.google-earth.kml+xml;charset=utf-8");
    else if (fmt === "EWKT") downloadText(`aoi_epsg${code}.ewkt.txt`, txt, "text/plain;charset=utf-8");
    else downloadText(`aoi_epsg${code}.wkt.txt`, txt, "text/plain;charset=utf-8");

    toast("Download gestartet.");
  });

  btnAltCopy.addEventListener("click", async () => {
    const txt = outAlt.value || "";
    if (!txt.trim()) return;
    try {
      await navigator.clipboard.writeText(txt);
      toast("Output kopiert.");
    } catch {
      toast("Kopieren fehlgeschlagen (Browser-Rechte).");
    }
  });

  // ---- init
  updateAll();
})();
"""

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
app.config["JSON_AS_ASCII"] = False

@app.after_request
def _add_headers(resp: Response) -> Response:
  resp.headers["Access-Control-Allow-Origin"] = "*"
  resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
  resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
  return resp

@app.get("/")
def index():
  return render_template_string(
    INDEX_HTML,
    title=APP_TITLE,
    start_lat=START_LAT,
    start_lon=START_LON,
    start_zoom=START_ZOOM,
  )

@app.get("/static/app.css")
def static_css():
  return Response(APP_CSS, mimetype="text/css; charset=utf-8")

@app.get("/static/app.js")
def static_js():
  return Response(APP_JS, mimetype="application/javascript; charset=utf-8")

@app.get("/api/healthz")
def healthz():
  return jsonify({"ok": True, "service": "aoi-studio"})

@app.get("/api/example")
def example():
  return jsonify({
    "type": "FeatureCollection",
    "features": [{
      "type": "Feature",
      "properties": {"epsg": 4326, "name": "example"},
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[8.64,49.88],[8.67,49.88],[8.67,49.86],[8.64,49.86],[8.64,49.88]]]
      }
    }]
  })

if __name__ == "__main__":
  port = int(os.getenv("PORT", "8080"))
  app.run(host="0.0.0.0", port=port, debug=True)
