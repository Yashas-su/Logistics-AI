import { useState, useEffect, useRef, useCallback } from "react";
import { useDisruptionEngine } from "./hooks/useDisruptionEngine";
import ShipmentPanel from "./components/ShipmentPanel";
import AlertFeed from "./components/AlertFeed";
import ScenarioPlayer from "./components/ScenarioPlayer";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || "";

// ── Topbar ────────────────────────────────────────────────────────────────
function Topbar() {
  const [time, setTime] = useState("");
  useEffect(() => {
    const t = setInterval(() => {
      setTime(new Date().toUTCString().slice(17, 25) + " UTC");
    }, 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="topbar">
      <div className="logo">Logistic<span>AI</span> — Operations Center</div>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{time}</span>
        <div className="live-pill"><div className="pulse" />Live</div>
      </div>
    </div>
  );
}

// ── KPI Bar ───────────────────────────────────────────────────────────────
function KPIBar({ total, atRisk, rerouted, onTimeRate }) {
  return (
    <div className="kpi-row">
      <div className="kpi">
        <div className="kpi-label">Active shipments</div>
        <div className="kpi-val">{total.toLocaleString()}</div>
        <div className="kpi-sub">across 14 carriers</div>
      </div>
      <div className="kpi">
        <div className="kpi-label">At risk</div>
        <div className="kpi-val" style={{ color: atRisk > 0 ? "var(--color-danger)" : "var(--color-success)" }}>
          {atRisk}
        </div>
        <div className="kpi-sub">{atRisk > 0 ? "disruption active" : "all clear"}</div>
      </div>
      <div className="kpi">
        <div className="kpi-label">Rerouted today</div>
        <div className="kpi-val" style={{ color: rerouted > 0 ? "var(--color-warning)" : "var(--text-primary)" }}>
          {rerouted}
        </div>
        <div className="kpi-sub">autonomous decisions</div>
      </div>
      <div className="kpi">
        <div className="kpi-label">On-time rate</div>
        <div className="kpi-val" style={{ color: "var(--color-success)" }}>{onTimeRate.toFixed(1)}%</div>
        <div className="kpi-sub">rolling 24h</div>
      </div>
    </div>
  );
}

// ── SVG Fallback Map (works without Mapbox token) ─────────────────────────
function SVGMap({ shipments, disruptions, mapMode }) {
  const projectLon = (lon) => ((lon + 125) / 59) * 500 + 20;
  const projectLat = (lat) => ((49 - lat) / 25) * 280 + 20;

  function riskColor(r) {
    if (r < 0.3) return "#1D9E75";
    if (r < 0.6) return "#BA7517";
    return "#E24B4A";
  }

  return (
    <svg width="100%" viewBox="0 0 540 320" style={{ display: "block", background: "#0f1923" }}>
      {/* Grid */}
      {[30, 90, 150, 210, 270].map(y => (
        <line key={y} x1="20" y1={y} x2="520" y2={y} stroke="#1e2f42" strokeWidth="0.4" />
      ))}
      {[80, 160, 240, 320, 400, 480].map(x => (
        <line key={x} x1={x} y1="20" x2={x} y2="300" stroke="#1e2f42" strokeWidth="0.4" />
      ))}

      {/* US outline approximation */}
      <path fill="#1a2535" stroke="#2d3f55" strokeWidth="0.8"
        d="M60,40 L100,35 L180,33 L260,32 L340,33 L400,36 L430,42 L445,55 L450,72
           L445,90 L438,108 L440,125 L446,140 L442,158 L428,168 L410,174 L390,178
           L368,182 L348,186 L328,188 L305,190 L285,192 L268,198 L258,210 L250,222
           L240,226 L228,224 L218,214 L208,205 L194,200 L178,196 L160,192 L140,188
           L118,184 L98,176 L78,166 L62,152 L50,135 L44,118 L44,100 L48,82 L52,64 Z"
      />

      {/* Disruption zones */}
      {disruptions.map((d, i) => {
        const cx = projectLon(d.lon);
        const cy = projectLat(d.lat);
        return (
          <g key={i}>
            <circle cx={cx} cy={cy} r={28} fill="#E24B4A" opacity={0.06} />
            <circle cx={cx} cy={cy} r={18} fill="#E24B4A" opacity={0.10} />
            <circle cx={cx} cy={cy} r={9}  fill="#E24B4A" opacity={0.22} />
            <text x={cx} y={cy + 22} textAnchor="middle" fontSize="8" fill="#F09595">
              Hurricane
            </text>
          </g>
        );
      })}

      {/* Hub markers */}
      {[
        ["SEA",  47.61,-122.33], ["LAX", 33.94,-118.41], ["DEN", 39.86,-104.67],
        ["DAL",  32.90, -97.04], ["HOU", 29.79, -95.37], ["CHI", 41.98, -87.91],
        ["MEM",  35.04, -89.98], ["ATL", 33.64, -84.43], ["MIA", 25.80, -80.28],
        ["NYC",  40.63, -73.78], ["BOS", 42.36, -71.01],
      ].map(([label, lat, lon]) => {
        const cx = projectLon(lon);
        const cy = projectLat(lat);
        const isDisrupted = disruptions.some(d => Math.abs(d.lat - lat) < 1.5 && Math.abs(d.lon - lon) < 2);
        return (
          <g key={label}>
            <circle cx={cx} cy={cy} r={4} fill={isDisrupted ? "#E24B4A" : "#1D9E75"} opacity={0.9} />
            <text x={cx} y={cy - 7} textAnchor="middle" fontSize="8"
              fill={isDisrupted ? "#F09595" : "#5DCAA5"}>{label}</text>
          </g>
        );
      })}

      {/* Shipment dots */}
      {shipments.map((s) => {
        const cx = projectLon(s.lon);
        const cy = projectLat(s.lat);
        return (
          <circle key={s.id} cx={cx} cy={cy} r={3.5}
            fill={riskColor(s.risk)}
            stroke="rgba(255,255,255,0.6)" strokeWidth={1}
            opacity={0.9}
          />
        );
      })}

      {/* Legend */}
      <g transform="translate(12,298)">
        <circle cx={6}   cy={6} r={4} fill="#1D9E75" />
        <text x={14}  y={10} fontSize={9} fill="#5DCAA5">On track</text>
        <circle cx={72}  cy={6} r={4} fill="#BA7517" />
        <text x={80}  y={10} fontSize={9} fill="#FAC775">Warning</text>
        <circle cx={140} cy={6} r={4} fill="#E24B4A" />
        <text x={148} y={10} fontSize={9} fill="#F09595">At risk</text>
      </g>
    </svg>
  );
}

// ── Map Card ──────────────────────────────────────────────────────────────
function MapCard({ shipments, disruptions, mapMode, setMapMode, onTriggerStorm, onReset, mapStatus }) {
  return (
    <div className="card">
      <div className="card-head">
        <span className="card-title">Live route map</span>
        <div className="mode-toggle">
          {["routes", "risk", "carriers"].map(m => (
            <button key={m} className={`mode-btn${mapMode === m ? " active" : ""}`}
              onClick={() => setMapMode(m)}>
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </button>
          ))}
        </div>
      </div>
      <div className="map-wrap">
        <SVGMap shipments={shipments} disruptions={disruptions} mapMode={mapMode} />
        {MAPBOX_TOKEN && (
          <div style={{ position: "absolute", bottom: 4, right: 8, fontSize: 9, color: "#4a6a8a" }}>
            Set VITE_MAPBOX_TOKEN for full Mapbox GL map
          </div>
        )}
      </div>
      <div className="btn-row">
        <button className="btn-danger" onClick={onTriggerStorm}>
          Simulate hurricane event
        </button>
        <button onClick={onReset}>Reset demo</button>
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{mapStatus}</span>
      </div>
    </div>
  );
}

// ── App ───────────────────────────────────────────────────────────────────
export default function App() {
  const [mapMode, setMapMode] = useState("routes");
  const [selectedId, setSelectedId] = useState(null);
  const { state, triggerStorm, reset } = useDisruptionEngine();

  return (
    <div className="dashboard-root">
      <Topbar />
      <KPIBar
        total={state.totalShipments}
        atRisk={state.atRisk}
        rerouted={state.reroutedToday}
        onTimeRate={state.onTimeRate}
      />
      <div className="main-grid">
        <MapCard
          shipments={state.shipments}
          disruptions={state.disruptions}
          mapMode={mapMode}
          setMapMode={setMapMode}
          onTriggerStorm={triggerStorm}
          onReset={reset}
          mapStatus={state.mapStatus}
        />
        <div className="right-col">
          <ShipmentPanel
            shipments={state.shipments}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
          <AlertFeed alerts={state.alerts} />
        </div>
      </div>
      <ScenarioPlayer timeline={state.timeline} />
    </div>
  );
}
