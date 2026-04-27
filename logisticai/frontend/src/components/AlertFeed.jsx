// AlertFeed.jsx
const COLORS = { danger: "#E24B4A", warning: "#BA7517", success: "#1D9E75", info: "#185FA5" };

export default function AlertFeed({ alerts }) {
  return (
    <div className="card" style={{ flex: 1 }}>
      <div className="card-head">
        <span className="card-title">Event feed</span>
        {alerts.length > 0 && (
          <span className="badge badge-danger">{alerts.length} active</span>
        )}
      </div>
      {alerts.length === 0 ? (
        <div style={{ padding: "20px 14px", textAlign: "center",
          color: "var(--text-tertiary)", fontSize: 12 }}>
          No active disruptions
        </div>
      ) : (
        <div style={{ maxHeight: 240, overflowY: "auto" }}>
          {alerts.map(a => (
            <div key={a.id} className="alert-item">
              <div className="alert-dot"
                style={{ background: COLORS[a.level] || "#888" }} />
              <div className="alert-body">
                <div className="alert-title">{a.title}</div>
                <div className="alert-meta">{a.meta}</div>
              </div>
              <div className="alert-time">
                {a.ts.toLocaleTimeString("en-US", { hour12: false })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
