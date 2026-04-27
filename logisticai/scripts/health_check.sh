#!/usr/bin/env bash
# LogisticAI health check — verifies all services are running
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}  [OK]${NC} $1"; }
fail() { echo -e "${RED}  [FAIL]${NC} $1"; }
warn() { echo -e "${YELLOW}  [WARN]${NC} $1"; }

echo ""
echo "LogisticAI — Service Health Check"
echo "=================================="

# Redis
if redis-cli -h localhost -p 6379 ping 2>/dev/null | grep -q PONG; then
  ok "Redis (localhost:6379)"
else
  fail "Redis (localhost:6379) — run: make infra-up"
fi

# Postgres
if pg_isready -h localhost -p 5432 -U logisticai 2>/dev/null; then
  ok "Postgres (localhost:5432)"
else
  fail "Postgres (localhost:5432) — run: make infra-up"
fi

# Kafka
if nc -z localhost 9092 2>/dev/null; then
  ok "Kafka (localhost:9092)"
else
  fail "Kafka (localhost:9092) — run: make infra-up"
fi

# Optimizer
if curl -sf http://localhost:8001/healthz 2>/dev/null | grep -q ok; then
  ok "Optimizer service (localhost:8001)"
else
  fail "Optimizer service — run: make run-optimizer"
fi

# Inference
if curl -sf http://localhost:8002/healthz 2>/dev/null | grep -q ok; then
  ok "Inference service (localhost:8002)"
else
  fail "Inference service — run: make run-inference"
fi

# WebSocket Hub
if curl -sf http://localhost:8080/healthz 2>/dev/null | grep -q ok; then
  ok "WebSocket hub (localhost:8080)"
else
  fail "WebSocket hub — run: make run-ws-hub"
fi

# Frontend
if curl -sf http://localhost:5173 2>/dev/null | grep -q LogisticAI; then
  ok "Frontend dashboard (localhost:5173)"
else
  warn "Frontend not running — run: make run-frontend"
fi

echo ""
echo "Grafana metrics: http://localhost:3001"
echo "Optimizer API docs: http://localhost:8001/docs"
echo "Inference API docs: http://localhost:8002/docs"
echo ""
