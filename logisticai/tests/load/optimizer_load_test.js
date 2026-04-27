/**
 * LogisticAI — k6 Load Test
 * Tests optimizer service at 1000 concurrent VUs.
 * Run: k6 run tests/load/optimizer_load_test.js -e API_BASE=http://localhost:8001
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const errorRate   = new Rate("errors");
const routeP99    = new Trend("route_latency_p99");
const rerouteP99  = new Trend("reroute_latency_p99");

export const options = {
  stages: [
    { duration: "1m",  target: 50   },
    { duration: "3m",  target: 500  },
    { duration: "3m",  target: 1000 },
    { duration: "2m",  target: 1000 },
    { duration: "1m",  target: 0    },
  ],
  thresholds: {
    "http_req_duration":   ["p(99)<200", "p(50)<50"],
    "errors":              ["rate<0.001"],
    "route_latency_p99":   ["p(99)<200"],
    "reroute_latency_p99": ["p(99)<250"],
  },
};

const BASE = __ENV.API_BASE || "http://localhost:8001";

const ORIGINS = ["HUB_SEA","HUB_LAX","HUB_DEN","HUB_DAL","HUB_CHI","HUB_MEM","HUB_ATL"];
const DESTS   = ["HUB_MIA","HUB_NYC","HUB_BOS","PORT_MIA","PORT_NYC","PORT_BMT","PORT_MSY"];

function randomItem(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

export default function () {
  const origin = randomItem(ORIGINS);
  const dest   = randomItem(DESTS);
  if (origin === dest) return;

  // Route computation
  const routeRes = http.post(
    `${BASE}/v1/routes/compute`,
    JSON.stringify({
      origin,
      destination: dest,
      weights: { cost: 0.4, time: 0.3, risk: 0.3 },
    }),
    { headers: { "Content-Type": "application/json" }, timeout: "5s" }
  );
  const routeOk = check(routeRes, {
    "route 200":      r => r.status === 200,
    "route has path": r => { try { return JSON.parse(r.body).route.length > 0; } catch { return false; } },
  });
  errorRate.add(!routeOk);
  routeP99.add(routeRes.timings.duration);

  sleep(0.05);

  // Reroute (simulate disruption)
  if (Math.random() < 0.1) {
    const sid = `SHP-${8000 + Math.floor(Math.random() * 2847)}`;
    const rerouteRes = http.post(
      `${BASE}/v1/shipments/${sid}/reroute`,
      JSON.stringify({
        shipment_id:   sid,
        exclude_nodes: ["HUB_HOU"],
        weights:       { cost: 0.4, time: 0.3, risk: 0.3 },
        reason:        "load_test",
      }),
      { headers: { "Content-Type": "application/json" }, timeout: "5s" }
    );
    const rerouteOk = check(rerouteRes, {
      "reroute 200": r => r.status === 200,
    });
    errorRate.add(!rerouteOk);
    rerouteP99.add(rerouteRes.timings.duration);
  }

  sleep(0.1);
}

export function handleSummary(data) {
  const p99 = data.metrics.http_req_duration?.values?.["p(99)"] || 0;
  const p50 = data.metrics.http_req_duration?.values?.["p(50)"] || 0;
  const err  = data.metrics.errors?.values?.rate || 0;
  console.log(`\nSummary: p50=${p50.toFixed(1)}ms p99=${p99.toFixed(1)}ms errors=${(err*100).toFixed(3)}%`);
  console.log(p99 < 200 ? "PASS: 200ms p99 SLO met" : "FAIL: p99 SLO breached");
  return { "tests/load/results.json": JSON.stringify(data, null, 2) };
}
