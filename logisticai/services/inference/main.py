"""
LogisticAI Inference Service
ML model serving with XGBoost ensemble and circuit breaker.
"""
import os, json, time, hashlib
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import redis.asyncio as aioredis
import numpy as np

load_dotenv()

from ml.ensemble import DelayEnsemble
from serving.circuit_breaker import MLCircuitBreaker

ensemble: DelayEnsemble = None
circuit_breaker: MLCircuitBreaker = None
redis_client = None

CACHE_TTL = int(os.getenv("INFERENCE_CACHE_TTL_SEC", 30))

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ensemble, circuit_breaker, redis_client
    print("Loading demo ML model...")
    ensemble = DelayEnsemble()
    ensemble.load_demo()
    circuit_breaker = MLCircuitBreaker(failure_threshold=5, recovery_timeout=30)
    redis_client = aioredis.from_url(
        f"redis://{os.getenv('REDIS_HOST','localhost')}:{os.getenv('REDIS_PORT',6379)}",
        decode_responses=True
    )
    print("Inference service ready.")
    yield
    await redis_client.aclose()

app = FastAPI(title="LogisticAI Inference Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class DelayFeatures(BaseModel):
    speed_deviation_pct: float = 0.0
    precip_intensity: float = 0.0
    congestion_level: float = 0.2
    segment_historical_delay_p50: float = 12.0
    carrier_on_time_rate_30d: float = 0.88
    port_wait_hours_rolling_7d: float = 1.5
    day_of_week: int = 1
    hour_of_day: int = 12
    customs_clearance_risk_score: float = 0.1
    vehicle_age_days: int = 365
    route_risk_composite: float = 0.15


def cache_key(features: dict) -> str:
    return "pred:" + hashlib.md5(
        json.dumps(features, sort_keys=True).encode()
    ).hexdigest()[:16]


async def primary_predict(features: dict) -> dict:
    return ensemble.predict(features)


async def fallback_predict(features: dict) -> dict:
    base = features.get("segment_historical_delay_p50", 15.0)
    risk_adj = base * (1 + features.get("congestion_level", 0) * 0.5)
    return {
        "delay_p10_minutes": round(max(0, risk_adj * 0.5), 1),
        "delay_p50_minutes": round(risk_adj, 1),
        "delay_p90_minutes": round(risk_adj * 2.2, 1),
        "risk_score": round(min(1.0, risk_adj / 240), 3),
        "uncertainty": 0.35,
        "source": "fallback_heuristic",
    }


@app.get("/healthz")
def health():
    return {"status": "ok", "circuit": circuit_breaker.state.value, "model": "demo_ensemble_v1"}


@app.post("/v1/predict/delay")
async def predict_delay(features: DelayFeatures):
    feat_dict = features.model_dump()
    key = cache_key(feat_dict)

    cached = await redis_client.get(key)
    if cached:
        result = json.loads(cached)
        result["source"] = "cache"
        return result

    t0 = time.monotonic()
    result = await circuit_breaker.call(primary_predict, fallback_predict, feat_dict)
    result["latency_ms"] = round((time.monotonic() - t0) * 1000, 2)

    await redis_client.setex(key, CACHE_TTL, json.dumps(result))
    return result


@app.post("/v1/predict/batch")
async def predict_batch(items: list[DelayFeatures]):
    results = []
    for item in items[:100]:
        feat_dict = item.model_dump()
        result = ensemble.predict(feat_dict)
        results.append(result)
    return {"predictions": results, "count": len(results)}


@app.get("/v1/model/info")
def model_info():
    return {
        "model_type": "XGBoost + LSTM Ensemble (demo)",
        "features": list(DelayFeatures.model_fields.keys()),
        "output": ["delay_p10_minutes", "delay_p50_minutes", "delay_p90_minutes", "risk_score"],
        "baseline_mae_minutes": 12.4,
        "circuit_breaker_state": circuit_breaker.state.value,
    }
