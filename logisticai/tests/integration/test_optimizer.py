"""
LogisticAI integration tests.
Run: cd tests && pytest integration/ -v --asyncio-mode=auto
"""
import pytest
import asyncio
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/optimizer"))

from optimizer.graph_model import build_demo_graph, Edge
from optimizer.astar_router import AStarRouter
from optimizer.rerouter import RealTimeRerouter
from decisions.autonomy_engine import AutonomyEngine, AutonomyLevel


# ── Graph tests ───────────────────────────────────────────────────────────

def test_demo_graph_has_expected_nodes():
    g = build_demo_graph()
    assert len(g.nodes) == 20
    assert "HUB_CHI" in g.nodes
    assert "HUB_HOU" in g.nodes
    assert "PORT_BMT" in g.nodes

def test_all_nodes_have_lat_lon():
    g = build_demo_graph()
    for node_id, meta in g.nodes.items():
        assert "lat" in meta, f"Node {node_id} missing lat"
        assert "lon" in meta, f"Node {node_id} missing lon"

def test_edges_are_bidirectional():
    g = build_demo_graph()
    chi_neighbors = {e.to_node for e in g.adjacency["HUB_CHI"]}
    assert "HUB_NYC" in chi_neighbors
    nyc_neighbors = {e.to_node for e in g.adjacency["HUB_NYC"]}
    assert "HUB_CHI" in nyc_neighbors

# ── Router tests ──────────────────────────────────────────────────────────

def test_astar_finds_route():
    g = build_demo_graph()
    r = AStarRouter(g)
    path, cost = r.find_route("HUB_SEA", "HUB_MIA",
                               weights={"cost": 0.33, "time": 0.34, "risk": 0.33})
    assert path[0] == "HUB_SEA"
    assert path[-1] == "HUB_MIA"
    assert len(path) >= 2
    assert cost > 0

def test_astar_respects_excluded_nodes():
    g = build_demo_graph()
    r = AStarRouter(g)
    path, _ = r.find_route("HUB_CHI", "PORT_BMT",
                             weights={"cost": 0.4, "time": 0.3, "risk": 0.3},
                             excluded_nodes=["HUB_HOU"])
    assert "HUB_HOU" not in path, "A* must avoid excluded nodes"

def test_astar_raises_when_no_route():
    g = build_demo_graph()
    r = AStarRouter(g)
    # Exclude so many nodes that no path exists
    excluded = ["HUB_DAL", "HUB_MEM", "HUB_ATL", "HUB_STL",
                "HUB_CHI", "HUB_MSP", "HUB_DEN", "HUB_PHX",
                "PORT_MSY", "PORT_BMT", "HUB_MIA", "PORT_MIA"]
    with pytest.raises(ValueError):
        r.find_route("HUB_HOU", "PORT_NYC",
                     weights={"cost": 0.33, "time": 0.34, "risk": 0.33},
                     excluded_nodes=excluded)

def test_astar_completes_under_200ms():
    import time
    g = build_demo_graph()
    r = AStarRouter(g)
    t0 = time.monotonic()
    r.find_route("HUB_SEA", "PORT_MIA",
                  weights={"cost": 0.4, "time": 0.3, "risk": 0.3})
    ms = (time.monotonic() - t0) * 1000
    assert ms < 200, f"Route took {ms:.1f}ms — SLO breach"

def test_composite_weight_increases_with_risk():
    low  = Edge("B", 1000, 500, risk_score=0.1, congestion=0.2, weather_penalty=0.0, transport_mode="road")
    high = Edge("B", 1000, 500, risk_score=0.9, congestion=0.2, weather_penalty=0.0, transport_mode="road")
    w = {"cost": 0.33, "time": 0.33, "risk": 0.34}
    assert high.composite_weight(w) > low.composite_weight(w)

def test_k_routes_returns_alternatives():
    g = build_demo_graph()
    r = AStarRouter(g)
    routes = r.find_k_routes("HUB_CHI", "HUB_MIA",
                              weights={"cost": 0.33, "time": 0.34, "risk": 0.33},
                              k=3)
    assert len(routes) >= 1
    for path, cost in routes:
        assert path[0] == "HUB_CHI"
        assert path[-1] == "HUB_MIA"

# ── Autonomy engine tests ─────────────────────────────────────────────────

def test_autonomy_auto_for_low_cost_high_confidence():
    e = AutonomyEngine()
    level = e.classify({"cost_delta_usd": 200, "old_risk": 0.9, "new_risk": 0.1, "confidence": 0.95})
    assert level == AutonomyLevel.FULLY_AUTONOMOUS

def test_autonomy_recommend_for_medium_cost():
    e = AutonomyEngine()
    level = e.classify({"cost_delta_usd": 3000, "old_risk": 0.5, "new_risk": 0.2, "confidence": 0.80})
    assert level == AutonomyLevel.RECOMMEND

def test_autonomy_escalate_for_very_high_cost():
    e = AutonomyEngine()
    level = e.classify({"cost_delta_usd": 80_000, "old_risk": 0.3, "new_risk": 0.1, "confidence": 0.60})
    assert level == AutonomyLevel.ESCALATE

def test_autonomy_escalate_for_low_confidence():
    e = AutonomyEngine()
    level = e.classify({"cost_delta_usd": 100, "old_risk": 0.8, "new_risk": 0.1, "confidence": 0.40})
    assert level == AutonomyLevel.ESCALATE

# ── Rerouter tests (async, no Redis required) ─────────────────────────────

@pytest.mark.asyncio
async def test_rerouter_avoids_disrupted_node():
    g = build_demo_graph()
    router = AStarRouter(g)
    rerouter = RealTimeRerouter(g, router, None, None)

    result = await rerouter._reroute_shipment("SHP-TEST", ["HUB_HOU"])
    assert "HUB_HOU" not in result["new_route"]
    assert result["reroute_reason"] == "disruption_detected"

@pytest.mark.asyncio
async def test_rerouter_returns_confidence():
    g = build_demo_graph()
    router = AStarRouter(g)
    rerouter = RealTimeRerouter(g, router, None, None)

    result = await rerouter._reroute_shipment("SHP-TEST", [])
    assert 0 < result["confidence"] <= 1.0
