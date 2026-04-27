const STEPS = [
  { label: "Webhook received",  t: "T+0s" },
  { label: "Graph updated",     t: "T+0.1s" },
  { label: "Affected found",    t: "T+0.3s" },
  { label: "A* rerouting",      t: "T+0.5s" },
  { label: "Carriers booked",   t: "T+1.2s" },
  { label: "Twin validated",    t: "T+4s" },
];
const PCTS = [0, 20, 40, 60, 80, 100];

export default function ScenarioPlayer({ timeline }) {
  const { step } = timeline;
  const pct = step >= 0 ? PCTS[Math.min(step, 5)] : 0;
  const done = pct === 100;

  return (
    <div className="card">
      <div className="card-head">
        <span className="card-title">Hurricane response timeline</span>
        <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
          {step < 0
            ? 'Press "Simulate hurricane event" to begin'
            : done
              ? "Complete — 11 reroutes in 4s · zero human intervention"
              : `Step ${step + 1} / ${STEPS.length}`}
        </span>
      </div>
      <div className="timeline-wrap">
        <div className="tl-track">
          <div className="tl-fill"
            style={{
              width: `${pct}%`,
              background: done ? "var(--color-success)" : "var(--color-info)",
            }} />
        </div>
        <div className="tl-steps">
          {STEPS.map((s, i) => {
            const isDone   = step > i;
            const isActive = step === i;
            return (
              <div key={i} className="tl-step">
                <div className={`tl-step-label${isDone ? " done" : isActive ? " active" : ""}`}>
                  {s.label}
                </div>
                <div className="tl-step-time">{s.t}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
