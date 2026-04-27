function riskColor(r) {
  if (r < 0.3) return "#1D9E75";
  if (r < 0.6) return "#BA7517";
  return "#A32D2D";
}

function StatusBadge({ status }) {
  const map = {
    on_track: ["badge-ok", "On track"],
    at_risk:  ["badge-danger", "At risk"],
    rerouted: ["badge-warn", "Rerouted"],
    delivered:["badge-info",  "Delivered"],
  };
  const [cls, label] = map[status] || ["badge-info", status];
  return <span className={`badge ${cls}`}>{label}</span>;
}

export default function ShipmentPanel({ shipments, selectedId, onSelect }) {
  const visible = shipments.slice(0, 12);
  return (
    <div className="card">
      <div className="card-head">
        <span className="card-title">Gulf corridor shipments</span>
        <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
          {shipments.length} tracked
        </span>
      </div>
      <table className="shp-table">
        <colgroup>
          <col style={{ width: "28%" }} />
          <col style={{ width: "24%" }} />
          <col style={{ width: "26%" }} />
          <col style={{ width: "22%" }} />
        </colgroup>
        <thead>
          <tr>
            {["ID", "Route", "Risk", "Status"].map(h => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visible.map(s => (
            <tr key={s.id} className="data-row"
              style={{ background: s.id === selectedId ? "var(--bg-info)" : "" }}
              onClick={() => onSelect(s.id)}>
              <td style={{ fontFamily: "monospace", fontSize: 11 }}>{s.id}</td>
              <td style={{ fontSize: 11, color: "var(--text-secondary)" }}>
                {s.from.replace("HUB_", "")} → {s.to.replace("HUB_","").replace("PORT_","")}
              </td>
              <td>
                <div className="risk-bar">
                  <div className="risk-track">
                    <div className="risk-fill"
                      style={{ width: `${Math.round(s.risk * 100)}%`, background: riskColor(s.risk) }} />
                  </div>
                  <span style={{ fontSize: 10, color: riskColor(s.risk), minWidth: 26 }}>
                    {Math.round(s.risk * 100)}%
                  </span>
                </div>
              </td>
              <td><StatusBadge status={s.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
