import { useReducer, useCallback } from "react";

const CORRIDORS = [
  { from: "HUB_CHI", to: "HUB_HOU", latRange: [35, 42], lonRange: [-97, -88] },
  { from: "HUB_DAL", to: "HUB_MIA", latRange: [25, 33], lonRange: [-97, -80] },
  { from: "HUB_LAX", to: "HUB_HOU", latRange: [29, 34], lonRange: [-118, -95] },
  { from: "HUB_SEA", to: "HUB_CHI", latRange: [41, 48], lonRange: [-122, -88] },
  { from: "HUB_NYC", to: "HUB_ATL", latRange: [33, 41], lonRange: [-84, -74] },
];

function makeShipment(i) {
  const corridor = CORRIDORS[i % CORRIDORS.length];
  const lat = corridor.latRange[0] + Math.random() * (corridor.latRange[1] - corridor.latRange[0]);
  const lon = corridor.lonRange[0] + Math.random() * (corridor.lonRange[1] - corridor.lonRange[0]);
  return {
    id: `SHP-${8000 + i}`,
    from: corridor.from,
    to: corridor.to,
    lat, lon,
    risk: 0.05 + Math.random() * 0.22,
    status: "on_track",
    carrier: ["FedEx Freight", "UPS Supply Chain", "XPO Logistics", "Old Dominion", "Knight-Swift"][i % 5],
  };
}

const BASE_SHIPMENTS = Array.from({ length: 22 }, (_, i) => makeShipment(i));

const INITIAL = {
  shipments: BASE_SHIPMENTS,
  totalShipments: 2847,
  atRisk: 0,
  reroutedToday: 0,
  onTimeRate: 94.2,
  disruptions: [],
  alerts: [],
  timeline: { step: -1 },
  mapStatus: "Monitoring 2,847 shipments",
};

function reducer(state, action) {
  switch (action.type) {
    case "STORM_WEBHOOK":
      return {
        ...state,
        alerts: [{ id: Date.now(), level: "danger",
          title: "Hurricane alert — Cat 3 landfall",
          meta: "Tomorrow.io webhook · severity 0.91 · duration 18h",
          ts: new Date() }, ...state.alerts],
        timeline: { step: 0 },
        mapStatus: "Disruption detected — analysing impact...",
      };
    case "GRAPH_UPDATED":
      return {
        ...state,
        disruptions: [{ lat: 29.76, lon: -95.37, severity: 0.91 }],
        alerts: [{ id: Date.now(), level: "warning",
          title: "Route risk scores updated",
          meta: "HUB_HOUSTON + PORT_HOUSTON · risk +0.40 applied",
          ts: new Date() }, ...state.alerts],
        timeline: { step: 1 },
      };
    case "AFFECTED_FOUND":
      return {
        ...state,
        shipments: state.shipments.map(s =>
          s.to === "HUB_HOU" || s.from === "HUB_HOU" || (s.lon > -97 && s.lon < -93 && s.lat < 33)
            ? { ...s, risk: Math.min(0.95, s.risk + 0.70), status: "at_risk",
                lat: 29.5 + Math.random() * 1.2, lon: -95.8 + Math.random() * 1.5 }
            : s
        ),
        atRisk: 11,
        alerts: [{ id: Date.now(), level: "danger",
          title: "11 shipments flagged at risk",
          meta: "Redis route-index scan complete · A* rerouting initiated",
          ts: new Date() }, ...state.alerts],
        timeline: { step: 2 },
        mapStatus: "11 shipments at risk — rerouting...",
      };
    case "REROUTING":
      return {
        ...state,
        alerts: [{ id: Date.now(), level: "warning",
          title: "A* rerouting — 11 routes computed",
          meta: "Excluded: HUB_HOUSTON, PORT_HOUSTON · avg +3.1h +$350",
          ts: new Date() }, ...state.alerts],
        timeline: { step: 3 },
      };
    case "COMMITTED":
      return {
        ...state,
        shipments: state.shipments.map(s =>
          s.status === "at_risk"
            ? { ...s, risk: Math.max(0.08, s.risk - 0.78), status: "rerouted",
                to: s.to === "HUB_HOU" ? "PORT_BMT" : s.to,
                lat: 30.1 + Math.random() * 1.5, lon: -93.8 - Math.random() * 2 }
            : s
        ),
        reroutedToday: 11,
        onTimeRate: 91.8,
        alerts: [{ id: Date.now(), level: "success",
          title: "Carrier capacity pre-booked",
          meta: "Beaumont + New Orleans confirmed · ETA delta +3.1h",
          ts: new Date() }, ...state.alerts],
        timeline: { step: 4 },
      };
    case "VALIDATED":
      return {
        ...state,
        atRisk: 0,
        alerts: [{ id: Date.now(), level: "success",
          title: "Digital twin validated",
          meta: "No bottleneck at BMT/MSY · 24h simulation horizon clear",
          ts: new Date() }, ...state.alerts],
        timeline: { step: 5 },
        mapStatus: "11 rerouted · risk 0.91 → 0.11 · zero human actions",
      };
    case "RESET":
      return INITIAL;
    default:
      return state;
  }
}

export function useDisruptionEngine() {
  const [state, dispatch] = useReducer(reducer, INITIAL);

  const triggerStorm = useCallback(() => {
    dispatch({ type: "STORM_WEBHOOK" });
    setTimeout(() => dispatch({ type: "GRAPH_UPDATED" }),   700);
    setTimeout(() => dispatch({ type: "AFFECTED_FOUND" }), 1600);
    setTimeout(() => dispatch({ type: "REROUTING" }),      2800);
    setTimeout(() => dispatch({ type: "COMMITTED" }),      4200);
    setTimeout(() => dispatch({ type: "VALIDATED" }),      6000);
  }, []);

  const reset = useCallback(() => dispatch({ type: "RESET" }), []);

  return { state, triggerStorm, reset };
}
