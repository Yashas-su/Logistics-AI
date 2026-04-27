import heapq
import math
from typing import Dict, List, Optional, Tuple

from optimizer.graph_model import LogisticsGraph, PriorityItem


class AStarRouter:
    def __init__(self, graph: LogisticsGraph):
        self.graph = graph

    def _heuristic(self, node_id: str, goal_id: str, weights: Dict) -> float:
        n = self.graph.nodes.get(node_id, {})
        g = self.graph.nodes.get(goal_id, {})
        if not n or not g:
            return 0.0
        lat_diff = n.get("lat", 0) - g.get("lat", 0)
        lon_diff = n.get("lon", 0) - g.get("lon", 0)
        euclidean_km = math.sqrt(lat_diff ** 2 + lon_diff ** 2) * 111.0
        return weights.get("time", 0.33) * (euclidean_km / 1000.0)

    def find_route(
        self,
        origin: str,
        destination: str,
        weights: Dict[str, float],
        excluded_nodes: Optional[List[str]] = None,
        max_cost_usd: Optional[float] = None,
    ) -> Tuple[List[str], float]:
        excluded = set(excluded_nodes or [])
        if origin in excluded:
            raise ValueError(f"Origin '{origin}' is in excluded nodes")

        g_score: Dict[str, float] = {origin: 0.0}
        f_score = {origin: self._heuristic(origin, destination, weights)}
        came_from: Dict[str, Optional[str]] = {origin: None}
        accumulated_cost: Dict[str, float] = {origin: 0.0}

        open_heap = [PriorityItem(f_score[origin], origin)]

        while open_heap:
            current = heapq.heappop(open_heap).node

            if current == destination:
                return self._reconstruct(came_from, destination), g_score[destination]

            for edge in self.graph.adjacency.get(current, []):
                neighbor = edge.to_node
                if neighbor in excluded:
                    continue

                tentative_cost = accumulated_cost[current] + edge.base_cost
                if max_cost_usd and tentative_cost > max_cost_usd:
                    continue

                edge_weight = edge.composite_weight(weights)
                tentative_g = g_score[current] + edge_weight

                if tentative_g < g_score.get(neighbor, math.inf):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    accumulated_cost[neighbor] = tentative_cost
                    f = tentative_g + self._heuristic(neighbor, destination, weights)
                    f_score[neighbor] = f
                    heapq.heappush(open_heap, PriorityItem(f, neighbor))

        raise ValueError(f"No feasible route from {origin} to {destination} "
                         f"(excluded: {excluded})")

    def _reconstruct(self, came_from: dict, current: str) -> List[str]:
        path = []
        while current is not None:
            path.append(current)
            current = came_from[current]
        return list(reversed(path))

    def find_k_routes(
        self,
        origin: str,
        destination: str,
        weights: Dict[str, float],
        k: int = 3,
    ) -> List[Tuple[List[str], float]]:
        """Yen's K-shortest paths — returns k alternative routes."""
        routes = []
        excluded_sets = [set()]

        primary_path, primary_cost = self.find_route(origin, destination, weights)
        routes.append((primary_path, primary_cost))

        for i in range(1, k):
            candidates = []
            prev_path = routes[i - 1][0]
            for j in range(len(prev_path) - 1):
                spur_node = prev_path[j]
                root_path = prev_path[:j + 1]
                excluded = set()
                for route, _ in routes:
                    if route[:j + 1] == root_path and j + 1 < len(route):
                        excluded.add(route[j + 1])
                excluded.update(root_path[:-1])
                try:
                    spur_path, spur_cost = self.find_route(
                        spur_node, destination, weights,
                        excluded_nodes=list(excluded)
                    )
                    total = root_path[:-1] + spur_path
                    total_cost = spur_cost + i * 0.1
                    if total not in [r[0] for r in routes]:
                        candidates.append((total, total_cost))
                except ValueError:
                    pass
            if not candidates:
                break
            candidates.sort(key=lambda x: x[1])
            routes.append(candidates[0])

        return routes
