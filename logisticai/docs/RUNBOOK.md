# LogisticAI — Operational Runbook

## RUNBOOK-001: Optimizer p99 > 200ms

**Severity:** P1  
**SLO:** p99 route computation < 200ms

### Diagnosis
```bash
# Check pod health
kubectl top pods -n logistics -l app=optimizer-service

# Check Redis hit rate (should be > 60%)
redis-cli info stats | grep keyspace_hits

# Check queue depth
curl http://localhost:8001/healthz
```

### Resolution
1. **Redis cold** → run `make seed` to warm cache
2. **OOM** → increase memory limit in `k8s/optimizer-deployment.yaml`
3. **Graph too large** → enable edge pruning (set `MAX_GRAPH_EDGES=5000`)

---

## RUNBOOK-002: ML circuit breaker open

**Symptom:** Inference service returning `"source":"fallback_heuristic"`

### Diagnosis
```bash
curl http://localhost:8002/v1/model/info | jq .circuit_breaker_state
```

### Resolution
1. Check if demo model loaded: `curl http://localhost:8002/healthz`
2. Restart inference service: `make run-inference`
3. Circuit auto-closes after 30s of successful predictions

---

## RUNBOOK-003: No shipments in dashboard

**Symptom:** Shipment table empty, map shows no dots

### Diagnosis
```bash
redis-cli keys "shipment:*" | head -5
redis-cli hgetall shipment:SHP-8000
```

### Resolution
```bash
make seed   # re-seed all shipment data
```

---

## RUNBOOK-004: WebSocket not connecting

**Symptom:** Dashboard shows no live updates

### Diagnosis
```bash
curl http://localhost:8080/healthz
# Check browser console for WebSocket errors
```

### Resolution
1. Ensure `make run-ws-hub` is running
2. Check `WS_HUB_PORT=8080` in `.env`
3. Browser: open DevTools → Network → WS tab to inspect frames

---

## RUNBOOK-005: Kafka consumer lag growing

**Symptom:** Events delayed > 5s

### Diagnosis
```bash
docker exec -it <kafka-container> \
  kafka-consumer-groups --bootstrap-server localhost:9092 \
  --describe --group logisticai-optimizer
```

### Resolution
1. Scale ingestion service (reduce emit interval)
2. Add Kafka partitions: increase `KAFKA_PARTITIONS=16`
3. Scale optimizer pods: `kubectl scale deployment/optimizer --replicas=5`

---

## Incident Response Template

```
INCIDENT: [brief description]
SEVERITY: P1 / P2 / P3
TIME DETECTED: 
TIME RESOLVED:

IMPACT:
- N shipments affected
- SLO breach of Xms at pYY

ROOT CAUSE:

TIMELINE:
T+0:  [detected]
T+N:  [actions taken]
T+M:  [resolved]

REMEDIATION:
- Immediate: 
- Long-term:
```
