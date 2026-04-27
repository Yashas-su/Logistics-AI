"""
LogisticAI Optimizer Service
A* routing engine with real-time disruption handling.
"""
import os, json, time, asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import redis.asyncio as aioredis
import jwt

load_dotenv()

from optimizer.graph_model import LogisticsGraph, Edge, build_demo_graph
from optimizer.astar_router import AStarRouter
from optimizer.rerouter import RealTimeRerouter
from decisions.autonomy_engine import AutonomyEngine, AutonomyLevel

# ── App lifecycle ─────────────────────────────────────────────────────────

graph: LogisticsGraph = None
router_engine: AStarRouter = None
rerouter: RealTimeRerouter = None
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph, router_engine, rerouter, redis_client
    print("Building logistics graph...")
    graph = build_demo_graph()
    router_engine = AStarRouter(graph)
    redis_client = aioredis.from_url(
        f"redis://{os.getenv('REDIS_HOST','localhost')}:{os.getenv('REDIS_PORT',6379)}",
        decode_responses=True
    )
    rerouter = RealTimeRerouter(graph, router_engine, None, redis_client)
    print(f"Graph ready: {len(graph.nodes)} nodes, optimizer online.")
    yield
    await redis_client.aclose()

app = FastAPI(
    title="LogisticAI Optimizer Service",
    description="A* routing engine with multi-constraint optimization and real-time rerouting",
    version="1.4.2",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

security = HTTPBearer(auto_error=False)
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production-use-256-bit-key")

def get_tenant(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    if not credentials:
        return "demo-tenant"
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload.get("tid", "demo-tenant")
    except Exception:
        return "demo-tenant"

# ── Models ────────────────────────────────────────────────────────────────

class WeightInput(BaseModel):
    cost: float = Field(0.33, ge=0, le=1)
    time: float = Field(0.34, ge=0, le=1)
    risk: float = Field(0.33, ge=0, le=1)

class ComputeRouteRequest(BaseModel):
    origin: str
    destination: str
    weights: WeightInput = WeightInput()
    exclude_nodes: list[str] = []
    max_cost_usd: Optional[float] = None

class RerouteRequest(BaseModel):
    shipment_id: str
    exclude_nodes: list[str] = []
    weights: WeightInput = WeightInput()
    reason: str = "manual"

class DisruptionRequest(BaseModel):
    disruption_id: str
    type: str
    affected_nodes: list[str]
    severity: float = Field(..., ge=0, le=1)
    duration_hours: int = 6

# ── Routes ────────────────────────────────────────────────────────────────

@app.get("/healthz")
def health(): return {"status": "ok", "nodes": len(graph.nodes)}

@app.get("/v1/graph/nodes")
def list_nodes(tenant: str = Depends(get_tenant)):
    return {"nodes": [
        {"id": nid, **meta}
        for nid, meta in graph.nodes.items()
    ]}

@app.post("/v1/routes/compute")
def compute_route(req: ComputeRouteRequest, tenant: str = Depends(get_tenant)):
    if req.origin not in graph.nodes:
        raise HTTPException(404, f"Origin node '{req.origin}' not found")
    if req.destination not in graph.nodes:
        raise HTTPException(404, f"Destination node '{req.destination}' not found")

    t0 = time.monotonic()
    try:
        path, cost = router_engine.find_route(
            origin=req.origin,
            destination=req.destination,
            weights=req.weights.model_dump(),
            excluded_nodes=req.exclude_nodes,
            max_cost_usd=req.max_cost_usd,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    elapsed_ms = (time.monotonic() - t0) * 1000
    return {
        "route": path,
        "total_cost_usd": round(cost * 10000, 2),
        "hops": len(path) - 1,
        "compute_ms": round(elapsed_ms, 2),
    }

@app.post("/v1/shipments/{shipment_id}/reroute")
async def reroute_shipment(
    shipment_id: str,
    req: RerouteRequest,
    tenant: str = Depends(get_tenant)
):
    shipment_data = await redis_client.hgetall(f"shipment:{shipment_id}")
    if not shipment_data:
        shipment_data = {
            "shipment_id": shipment_id,
            "current_hub": list(graph.nodes.keys())[0],
            "destination": list(graph.nodes.keys())[-1],
            "current_route": json.dumps([]),
            "current_route_cost": "0",
            "optimization_weights": json.dumps(req.weights.model_dump()),
        }

    t0 = time.monotonic()
    result = await rerouter._reroute_shipment(shipment_id, req.exclude_nodes)
    elapsed_ms = (time.monotonic() - t0) * 1000

    engine = AutonomyEngine()
    level = engine.classify({
        "cost_delta_usd": abs(result.get("cost_delta_usd", 0)),
        "old_risk": 0.85,
        "new_risk": 0.12,
        "confidence": result.get("confidence", 0.9),
    })

    return {**result, "autonomy_level": level.value, "compute_ms": round(elapsed_ms, 2)}

@app.post("/v1/disruptions/handle")
async def handle_disruption(req: DisruptionRequest, tenant: str = Depends(get_tenant)):
    event = req.model_dump()
    affected_shipments = await rerouter._find_affected_shipments(req.affected_nodes)

    results = []
    for sid in affected_shipments[:50]:
        try:
            r = await rerouter._reroute_shipment(sid, req.affected_nodes)
            results.append({"shipment_id": sid, "status": "rerouted", **r})
        except Exception as e:
            results.append({"shipment_id": sid, "status": "failed", "error": str(e)})

    return {
        "disruption_id": req.disruption_id,
        "affected_count": len(affected_shipments),
        "processed": len(results),
        "reroutes": results,
    }

@app.get("/v1/analytics/graph-stats")
def graph_stats(tenant: str = Depends(get_tenant)):
    total_edges = sum(len(edges) for edges in graph.adjacency.values())
    avg_risk = sum(
        e.risk_score
        for edges in graph.adjacency.values()
        for e in edges
    ) / max(total_edges, 1)
    return {
        "total_nodes": len(graph.nodes),
        "total_edges": total_edges,
        "avg_edge_risk": round(avg_risk, 4),
    }
