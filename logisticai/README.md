# LogisticAI — Production Supply Chain Optimization Platform

A Google-level, production-grade logistics and dynamic supply chain optimization platform that continuously analyzes real-time and historical transit data to predict disruptions and automatically re-routes shipments before delays occur.

---

## Architecture Overview

```
GPS/IoT → Pub/Sub → Apache Beam → Feature Store → ML Ensemble → A* Optimizer → WebSocket Hub → React Dashboard
                         ↓
                    BigQuery Warehouse
                         ↓
                  Vertex AI Retraining
```

**Stack:** Python (optimizer, ML, pipelines) · Go (WebSocket hub) · React + Mapbox GL (frontend) · GCP (Pub/Sub, BigQuery, Spanner, Vertex AI, GKE) · Terraform · Docker Compose (local dev)

---

## Quick Start (Local Development — 10 minutes)

### Prerequisites

| Tool | Version | Install |
|---|---|---|
| Docker Desktop | 4.x+ | https://docs.docker.com/get-docker |
| Docker Compose | v2+ | included with Docker Desktop |
| Node.js | 18+ | https://nodejs.org |
| Python | 3.11+ | https://python.org |
| Go | 1.21+ | https://go.dev |
| make | any | pre-installed on macOS/Linux |

### 1. Clone and configure

```bash
git clone <repo-url> logisticai
cd logisticai
cp .env.example .env
```

Edit `.env` — the defaults work for local development with no cloud credentials required. To enable the full Mapbox map, add your free Mapbox token.

### 2. Start infrastructure

```bash
make infra-up
```

This starts (via Docker Compose):
- **Redis** on `localhost:6379` — shipment state cache
- **Kafka + Zookeeper** on `localhost:9092` — event streaming (Pub/Sub emulator)
- **PostgreSQL** on `localhost:5432` — local Spanner substitute
- **Prometheus + Grafana** on `localhost:3001` — metrics dashboard

Wait for all containers to report healthy (~30 seconds):
```bash
make infra-status
```

### 3. Seed demo data

```bash
make seed
```

Loads 2,847 simulated shipments across US corridors with realistic GPS positions, carrier assignments, and risk scores.

### 4. Start backend services

Open four terminal tabs:

**Tab 1 — Optimizer service**
```bash
make run-optimizer
```
Starts the A* routing engine on `http://localhost:8001`

**Tab 2 — Inference service**
```bash
make run-inference
```
Starts the ML prediction gateway on `http://localhost:8002`
(Uses a pre-trained demo model — no Vertex AI needed locally)

**Tab 3 — Ingestion + stream simulator**
```bash
make run-ingestion
```
Starts the GPS event simulator — emits shipment position updates every 5 seconds, simulating 2,847 trucks in motion

**Tab 4 — WebSocket hub**
```bash
make run-ws-hub
```
Starts the Go WebSocket hub on `ws://localhost:8080`

### 5. Start the frontend

```bash
make run-frontend
```

Opens `http://localhost:5173` — the live operations dashboard.

### 6. Run the hurricane demo

With everything running, open the dashboard and click **"Simulate hurricane event"**. Watch the system:

1. Detect 11 shipments routed through Houston
2. Elevate their risk scores to 0.91+
3. Run A* rerouting with Houston excluded
4. Commit reroutes autonomously (no human action)
5. Update the live map in real time

Full demo completes in ~4 seconds.

---

## Running Individual Components

### Optimizer only (for API testing)

```bash
cd services/optimizer
pip install -r requirements.txt
python main.py

# Test a route computation
curl -X POST http://localhost:8001/v1/routes/compute \
  -H "Content-Type: application/json" \
  -d '{"origin":"HUB_CHI","destination":"PORT_BMT","weights":{"cost":0.4,"time":0.3,"risk":0.3}}'
```

### ML inference only

```bash
cd services/inference
pip install -r requirements.txt
python main.py

# Test delay prediction
curl -X POST http://localhost:8002/v1/predict/delay \
  -H "Content-Type: application/json" \
  -d '{"speed_deviation_pct":-0.3,"precip_intensity":0.8,"congestion_level":0.7,"segment_historical_delay_p50":15,"carrier_on_time_rate_30d":0.82,"port_wait_hours_rolling_7d":2.1,"day_of_week":1,"hour_of_day":14,"customs_clearance_risk_score":0.1,"vehicle_age_days":400,"route_risk_composite":0.4}'
```

### Run all tests

```bash
make test
```

### Run load test (requires k6)

```bash
make load-test
```

Ramps to 1000 VUs and validates the 200ms p99 SLO.

---

## Project Structure

```
logisticai/
├── services/
│   ├── optimizer/          # A* routing engine (Python/FastAPI)
│   ├── inference/          # ML model serving (Python/FastAPI)
│   ├── ingestion/          # GPS event ingestor + stream simulator
│   ├── websocket-hub/      # Real-time push server (Go)
│   └── digital-twin/       # SimPy discrete-event simulator
├── pipelines/
│   ├── shipment_stream_pipeline.py   # Apache Beam streaming job
│   └── dags/                          # Airflow DAGs for batch ETL
├── ml/
│   ├── train_delay_model.py           # XGBoost training script
│   ├── lstm_delay_model.py            # LSTM + attention model
│   ├── gnn_anomaly.py                 # Graph Neural Network anomaly detection
│   └── monitoring/drift_detector.py  # KS-test drift detection
├── frontend/                          # React + Mapbox GL dashboard
├── proto/logistics/v1/                # gRPC protobuf definitions
├── terraform/                         # GCP infrastructure as code
├── k8s/                               # Kubernetes manifests
├── tests/                             # Integration + load tests
├── scripts/                           # Seed data, health checks
└── docs/                              # Architecture, API, runbook docs
```

---

## Cloud Deployment (GCP)

### Prerequisites

- GCP project with billing enabled
- `gcloud` CLI authenticated
- Terraform 1.5+

### Deploy

```bash
cd terraform
terraform init
terraform plan -var="project_id=YOUR_PROJECT_ID"
terraform apply -var="project_id=YOUR_PROJECT_ID"
```

Full GCP deployment takes ~15 minutes and provisions:
- GKE Autopilot cluster (2 regions)
- Cloud Pub/Sub topics and subscriptions
- BigQuery datasets and tables
- Cloud Spanner instance
- Vertex AI endpoints
- Memorystore Redis
- Cloud Armor WAF policy
- All IAM bindings with least privilege

After apply, push service images and deploy:
```bash
make docker-build
make docker-push PROJECT_ID=YOUR_PROJECT_ID
make k8s-deploy PROJECT_ID=YOUR_PROJECT_ID
```

---

## Environment Variables

See `.env.example` for all variables. Key ones:

| Variable | Local default | Description |
|---|---|---|
| `DEMO_MODE` | `true` | Use local simulators instead of real APIs |
| `REDIS_HOST` | `localhost` | Redis host |
| `KAFKA_BROKER` | `localhost:9092` | Kafka broker |
| `DB_URL` | `postgresql://...` | PostgreSQL (local Spanner substitute) |
| `JWT_SECRET` | `dev-secret-change-me` | JWT signing key |
| `VITE_MAPBOX_TOKEN` | `` | Mapbox GL token (optional — uses SVG fallback if empty) |
| `GCP_PROJECT_ID` | `` | GCP project (cloud deployment only) |
| `VERTEX_ENDPOINT_ID` | `` | Vertex AI endpoint (cloud only) |

---

## API Reference

Full OpenAPI spec at `http://localhost:8001/docs` when optimizer is running.

### Key endpoints

```
POST /v1/routes/compute          Compute optimal route
POST /v1/shipments/{id}/reroute  Trigger reroute for a shipment
GET  /v1/shipments               List shipments with filtering
GET  /v1/disruptions             Active disruptions
GET  /v1/analytics/risk-heatmap  GeoJSON risk scores
WS   ws://localhost:8080/ws/shipments  Real-time shipment stream
```

---

## Docs

- `docs/ARCHITECTURE.md` — full system design with diagrams
- `docs/API.md` — complete API reference
- `docs/RUNBOOK.md` — operational runbooks and on-call playbooks

---

## License

MIT
