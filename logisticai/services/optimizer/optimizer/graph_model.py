import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(order=True)
class PriorityItem:
    priority: float
    node: str = field(compare=False)


@dataclass
class Edge:
    to_node: str
    base_distance: float
    base_cost: float
    risk_score: float
    congestion: float
    weather_penalty: float
    transport_mode: str

    def composite_weight(self, weights: Dict[str, float]) -> float:
        normalized_distance = self.base_distance / 1000.0
        time_factor = normalized_distance * (1 + self.congestion * 2)
        risk_factor = self.risk_score * (1 + self.weather_penalty)
        return (
            weights.get("cost", 0.33) * self.base_cost / 10_000
            + weights.get("time", 0.33) * time_factor
            + weights.get("risk", 0.34) * risk_factor
        )


class LogisticsGraph:
    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.adjacency: Dict[str, List[Edge]] = {}

    def add_node(self, node_id: str, **meta):
        self.nodes[node_id] = meta
        self.adjacency.setdefault(node_id, [])

    def add_edge(self, from_node: str, edge: Edge):
        self.adjacency[from_node].append(edge)

    def update_edge_risk(self, from_node: str, to_node: str, new_risk: float):
        for edge in self.adjacency.get(from_node, []):
            if edge.to_node == to_node:
                edge.risk_score = min(1.0, new_risk)
                break


def build_demo_graph() -> LogisticsGraph:
    """Build a realistic US logistics graph with 20 nodes."""
    g = LogisticsGraph()

    hubs = [
        ("HUB_SEA",  47.61, -122.33, "Seattle, WA"),
        ("HUB_LAX",  33.94, -118.41, "Los Angeles, CA"),
        ("HUB_DEN",  39.86, -104.67, "Denver, CO"),
        ("HUB_DAL",  32.90, -97.04,  "Dallas, TX"),
        ("HUB_HOU",  29.79, -95.37,  "Houston, TX"),
        ("HUB_CHI",  41.98, -87.91,  "Chicago, IL"),
        ("HUB_MEM",  35.04, -89.98,  "Memphis, TN"),
        ("HUB_ATL",  33.64, -84.43,  "Atlanta, GA"),
        ("HUB_MIA",  25.80, -80.28,  "Miami, FL"),
        ("HUB_NYC",  40.63, -73.78,  "New York, NY"),
        ("HUB_BOS",  42.36, -71.01,  "Boston, MA"),
        ("HUB_PHX",  33.44, -112.01, "Phoenix, AZ"),
        ("HUB_MSP",  44.88, -93.22,  "Minneapolis, MN"),
        ("HUB_STL",  38.75, -90.37,  "St. Louis, MO"),
        ("PORT_LAX", 33.74, -118.27, "Port of Los Angeles"),
        ("PORT_HOU", 29.73, -95.28,  "Port of Houston"),
        ("PORT_NYC", 40.68, -74.04,  "Port of New York"),
        ("PORT_MIA", 25.77, -80.17,  "Port of Miami"),
        ("PORT_BMT", 30.08, -94.10,  "Port of Beaumont (alt)"),
        ("PORT_MSY", 29.95, -90.25,  "Port of New Orleans (alt)"),
    ]

    for node_id, lat, lon, label in hubs:
        throughput = 200 if node_id.startswith("PORT") else 150
        g.add_node(node_id, lat=lat, lon=lon, label=label,
                   throughput_per_hour=throughput, avg_process_minutes=45)

    def add_bidir(g, a, b, dist, cost, risk=0.1, cong=0.2, weather=0.0, mode="road"):
        g.add_edge(a, Edge(b, dist, cost, risk, cong, weather, mode))
        g.add_edge(b, Edge(a, dist, cost, risk, cong, weather, mode))

    # Road connections
    add_bidir(g, "HUB_SEA",  "HUB_DEN",  2100, 1100, 0.10, 0.15)
    add_bidir(g, "HUB_SEA",  "HUB_LAX",  1800,  950, 0.08, 0.30)
    add_bidir(g, "HUB_LAX",  "HUB_PHX",   600,  320, 0.07, 0.25)
    add_bidir(g, "HUB_LAX",  "PORT_LAX",   35,   50, 0.05, 0.40)
    add_bidir(g, "HUB_PHX",  "HUB_DAL",  1450,  760, 0.09, 0.20)
    add_bidir(g, "HUB_DEN",  "HUB_DAL",  1300,  680, 0.08, 0.18)
    add_bidir(g, "HUB_DEN",  "HUB_CHI",  1600,  840, 0.09, 0.22)
    add_bidir(g, "HUB_DAL",  "HUB_HOU",   400,  250, 0.10, 0.28)
    add_bidir(g, "HUB_DAL",  "HUB_MEM",   800,  420, 0.08, 0.20)
    add_bidir(g, "HUB_DAL",  "PORT_BMT",  460,  280, 0.09, 0.18)
    add_bidir(g, "HUB_HOU",  "PORT_HOU",   35,   55, 0.06, 0.35)
    add_bidir(g, "HUB_HOU",  "PORT_BMT",  115,   90, 0.08, 0.20)
    add_bidir(g, "HUB_HOU",  "PORT_MSY",  360,  220, 0.09, 0.22)
    add_bidir(g, "HUB_MEM",  "HUB_CHI",   800,  420, 0.08, 0.25)
    add_bidir(g, "HUB_MEM",  "HUB_ATL",   700,  370, 0.07, 0.22)
    add_bidir(g, "HUB_MEM",  "HUB_STL",   360,  190, 0.06, 0.18)
    add_bidir(g, "HUB_CHI",  "HUB_MSP",   660,  350, 0.09, 0.22)
    add_bidir(g, "HUB_CHI",  "HUB_STL",   480,  255, 0.07, 0.28)
    add_bidir(g, "HUB_CHI",  "HUB_NYC",  1400,  740, 0.10, 0.30)
    add_bidir(g, "HUB_ATL",  "HUB_MIA",  1100,  580, 0.08, 0.20)
    add_bidir(g, "HUB_ATL",  "HUB_NYC",  1400,  740, 0.09, 0.25)
    add_bidir(g, "HUB_ATL",  "PORT_MSY", 1000,  530, 0.09, 0.20)
    add_bidir(g, "HUB_MIA",  "PORT_MIA",   35,   55, 0.05, 0.30)
    add_bidir(g, "HUB_NYC",  "PORT_NYC",   35,   60, 0.06, 0.45)
    add_bidir(g, "HUB_NYC",  "HUB_BOS",   340,  180, 0.07, 0.35)
    add_bidir(g, "HUB_STL",  "HUB_MSP",   700,  370, 0.08, 0.20)

    # Sea lanes (lower cost, higher transit time encoded as higher distance)
    add_bidir(g, "PORT_LAX", "PORT_HOU", 5800, 1200, 0.12, 0.05, 0.10, "sea")
    add_bidir(g, "PORT_HOU", "PORT_MIA", 1800,  420, 0.10, 0.05, 0.08, "sea")
    add_bidir(g, "PORT_MIA", "PORT_NYC", 2200,  490, 0.09, 0.04, 0.06, "sea")
    add_bidir(g, "PORT_BMT", "PORT_MSY",  350,  110, 0.08, 0.05, 0.07, "sea")

    return g
