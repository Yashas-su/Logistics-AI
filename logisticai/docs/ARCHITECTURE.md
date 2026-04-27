# LogisticAI — Architecture Documentation

## System Overview

LogisticAI is a production-grade, distributed supply chain optimization platform.
It processes real-time GPS, weather, and traffic data to predict shipment delays
and autonomously reroute affected shipments before disruptions cause delays.

## Component Responsibilities

### optimizer-service (Python/FastAPI, port 8001)
- A* routing engine with multi-constraint optimization (cost/time/risk)
- Real-time disruption handler — identifies and reroutes affected shipments
- Tiered autonomy engine — auto/recommend/escalate based on cost and confidence
- Exposes REST API consumed by the frontend and WebSocket hub

### inference-service (Python/FastAPI, port 8002)
- XGBoost + LSTM ensemble for delay prediction
- Monte Carlo Dropout for uncertainty-aware risk scoring (p10/p50/p90)
- Redis-cached predictions (30s TTL)
- Circuit breaker falls back to heuristic if model endpoint fails

### ingestion-service (Python, no port)
- Simulates GPS events from 2,847 trucks every 5 seconds
- Writes position updates to Redis Streams and Kafka topics
- Randomly emits disruption events for demo purposes

### websocket-hub (Go, port 8080)
- Fans out real-time events to browser WebSocket clients
- Per-client subscribe filters (shipment IDs, risk threshold, event types)
- Goroutine-per-client; 50K connections per pod at ~5MB RAM

### frontend (React + Vite, port 5173)
- Live SVG map (no Mapbox token required) or Mapbox GL JS (with token)
- Hurricane demo scenario with 6-step animated timeline
- Real-time shipment table with risk bars and status badges
- Alert feed with severity color-coding

## Data Flow

```
GPS Device
    │ MQTT/HTTP
    ▼
Ingestion Service → Redis Stream (stream:gps-events)
                  → Kafka topic  (shipment-gps-events)
    │
    ▼
Inference Service ← Redis cache lookup (30s TTL)
    │               Vertex AI / demo ensemble
    ▼
Risk score written to Redis (shipment:{id} hash)
    │
    ▼
Disruption Event (weather-alerts topic)
    │
    ▼
Optimizer Service
    ├── Find affected shipments (Redis set: shipments_via:{node})
    ├── A* reroute (concurrent, asyncio.gather)
    ├── Autonomy classification
    └── Commit to Redis + Postgres + WebSocket Hub
         │
         ▼
WebSocket Hub → Browser clients (dashboard update)
```

## Scaling Guide

| Load | Config |
|---|---|
| <100K shipments/day | Single pod per service, 1 Redis node, 1 Postgres |
| 1M shipments/day | 3 optimizer pods, Redis Cluster 3 nodes, read replica |
| 10M shipments/day | 10+ optimizer pods, Redis Cluster 16 nodes, Spanner |
| 100M shipments/day | GKE Autopilot + Kafka 512 partitions + Spanner multi-region |

## Security Notes (local dev)

- JWT secret is hardcoded in `.env.example` — change before any production use
- No TLS in local dev — add nginx/Caddy in front for staging/prod
- Redis has no auth in local dev — add `requirepass` for staging/prod
- Postgres uses `logisticai_dev` password — change for any non-local environment

## Cloud Deployment

See `terraform/` for full GCP infrastructure.
See `k8s/` for Kubernetes manifests.
See `docs/RUNBOOK.md` for operational runbooks.
