import React, { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";

const BASE = import.meta.env.BASE_URL;

function titleCase(slug) {
  return slug
    .split("_")
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}

function money(n) {
  return "$" + n.toLocaleString("en-US");
}

async function fetchJson(path) {
  const r = await fetch(BASE + path);
  if (!r.ok) {
    throw new Error(
      `${path} not found. Run "python -m pipeline.run" to generate data.`
    );
  }
  return r.json();
}

export default function App() {
  const [instance, setInstance] = useState(null);
  const [permits, setPermits] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [jurisdiction, setJurisdiction] = useState("all");
  const [layer, setLayer] = useState("all");
  const [selected, setSelected] = useState(null);
  const mapEl = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef(null);

  useEffect(() => {
    Promise.all([
      fetchJson("instance.json"),
      fetchJson("permits.json"),
      fetchJson("summary.json"),
    ])
      .then(([inst, p, s]) => {
        setInstance(inst);
        setPermits(p);
        setSummary(s);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!instance || !mapEl.current || mapRef.current) return;
    const map = L.map(mapEl.current, { scrollWheelZoom: false }).setView(
      instance.map.center,
      instance.map.zoom
    );
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    mapRef.current = map;
    markersRef.current = L.layerGroup().addTo(map);
    document.documentElement.style.setProperty(
      "--accent",
      instance.branding.colors.accent
    );
    document.documentElement.style.setProperty(
      "--bg",
      instance.branding.colors.bg
    );
    document.documentElement.style.setProperty(
      "--ink",
      instance.branding.colors.ink
    );
  }, [instance]);

  const visible = useMemo(() => {
    if (!permits) return [];
    return permits.filter(
      (p) =>
        (jurisdiction === "all" || p.jurisdiction === jurisdiction) &&
        (layer === "all" || p.layer === layer)
    );
  }, [permits, jurisdiction, layer]);

  useEffect(() => {
    if (!markersRef.current || !instance) return;
    markersRef.current.clearLayers();
    for (const p of visible) {
      if (p.lat == null) continue;
      const isFeature = p.layer === "feature";
      L.circleMarker([p.lat, p.lon], {
        radius: isFeature ? 8 : 4,
        color: isFeature ? instance.branding.colors.accent : "#666",
        weight: 2,
        fillColor: isFeature ? instance.branding.colors.accent : "#999",
        fillOpacity: 0.6,
      })
        .on("click", () => setSelected(p))
        .addTo(markersRef.current);
    }
  }, [visible, instance]);

  if (error) return <div className="error">{error}</div>;
  if (!instance || !permits || !summary) {
    return <div className="loading">Loading development report…</div>;
  }

  const months = Object.keys(summary.months).sort().reverse();
  const latest = months[0];
  const latestByJur = summary.months[latest];
  const jurisdictions = instance.jurisdictions;

  return (
    <div className="app">
      <header>
        <div>
          <h1>{instance.branding.title}</h1>
          <p className="subtitle">
            {instance.branding.subtitle} ·{" "}
            {new Date(latest + "-15").toLocaleDateString("en-US", {
              month: "long",
              year: "numeric",
            })}
          </p>
        </div>
        {instance.sponsor.zone_id && (
          <div className="sponsor" data-zone={instance.sponsor.zone_id}>
            {instance.sponsor.label}
          </div>
        )}
      </header>

      <div className="ledger">
        {jurisdictions.map((j) => {
          const s = latestByJur[j];
          if (!s) return null;
          return (
            <div className="ledger-cell" key={j}>
              <span className="ledger-place">{titleCase(j)}</span>
              <span className="ledger-val">{money(s.valuation)}</span>
              <span className="ledger-count">{s.permits_issued} permits</span>
            </div>
          );
        })}
      </div>

      <div ref={mapEl} className="map" />

      <div className="controls">
        <select
          value={jurisdiction}
          onChange={(e) => setJurisdiction(e.target.value)}
        >
          <option value="all">All jurisdictions</option>
          {jurisdictions.map((j) => (
            <option key={j} value={j}>
              {titleCase(j)}
            </option>
          ))}
        </select>
        <select value={layer} onChange={(e) => setLayer(e.target.value)}>
          <option value="all">All permits</option>
          <option value="feature">Major projects</option>
          <option value="standard">Standard permits</option>
        </select>
        <span className="count">{visible.length} shown</span>
      </div>

      {selected && (
        <div className="card">
          <button className="card-close" onClick={() => setSelected(null)}>
            Close
          </button>
          <h2>{selected.address}</h2>
          <p className="card-meta">
            {selected.template} · issued {selected.issue_date} ·{" "}
            {titleCase(selected.jurisdiction)}
          </p>
          {selected.contractor && (
            <p>
              <strong>Contractor:</strong> {selected.contractor}
            </p>
          )}
          {selected.owner && (
            <p>
              <strong>Owner:</strong> {selected.owner}
            </p>
          )}
          {(selected.finished_sqft || selected.units) && (
            <p className="card-data">
              {selected.finished_sqft
                ? `${selected.finished_sqft.toLocaleString()} sq ft finished`
                : ""}
              {selected.finished_sqft && selected.units ? " · " : ""}
              {selected.units ? `${selected.units} unit(s)` : ""}
            </p>
          )}
          <p className="card-desc">{selected.description}</p>
          {instance.property_history_url && selected.parcel_id && (
            <a
              href={instance.property_history_url.replace(
                "{parcel_id}",
                selected.parcel_id
              )}
              target="_blank"
              rel="noreferrer"
            >
              View property history
            </a>
          )}
        </div>
      )}

      <ul className="list">
        {visible.slice(0, 100).map((p) => (
          <li
            key={p.source_permit_id}
            className={p.layer}
            onClick={() => setSelected(p)}
          >
            <span className="list-template">{p.template}</span>
            <span className="list-address">{p.address}</span>
            <span className="list-date">{p.issue_date}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
