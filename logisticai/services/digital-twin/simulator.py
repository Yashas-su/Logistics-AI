"""
LogisticAI Digital Twin — SimPy discrete-event simulator.
Validates proposed reroutes before committing carrier bookings.
"""
import simpy
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class Hub:
    id: str
    throughput_per_hour: int
    avg_process_minutes: int = 45

class SupplyChainSimulator:
    def __init__(self, hubs: List[Hub], proposed_routes: Dict[str, List[str]],
                 time_horizon_hours: int = 24):
        self.env = simpy.Environment()
        self.hubs = {h.id: h for h in hubs}
        self.proposed_routes = proposed_routes
        self.horizon = time_horizon_hours * 60
        self.hub_resources: Dict[str, simpy.Resource] = {}

    def setup(self):
        for hub_id, hub in self.hubs.items():
            self.hub_resources[hub_id] = simpy.Resource(
                self.env, capacity=hub.throughput_per_hour
            )

    def shipment_process(self, route: List[str], shipment_id: str, results: list):
        for hub_id in route:
            if hub_id not in self.hub_resources:
                continue
            resource = self.hub_resources[hub_id]
            with resource.request() as req:
                yield req
                yield self.env.timeout(self.hubs[hub_id].avg_process_minutes)
        results.append({"shipment_id": shipment_id, "completed_at": self.env.now})

    def run(self) -> dict:
        self.setup()
        results = []
        for shipment_id, route in self.proposed_routes.items():
            self.env.process(self.shipment_process(route, shipment_id, results))
        self.env.run(until=self.horizon)
        bottlenecks = [
            hub_id for hub_id, res in self.hub_resources.items()
            if res.count > res.capacity * 1.5
        ]
        return {
            "completed_shipments": len(results),
            "bottleneck_hubs": bottlenecks,
            "simulation_valid": len(bottlenecks) == 0,
        }
