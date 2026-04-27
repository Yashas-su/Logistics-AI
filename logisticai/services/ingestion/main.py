"""
LogisticAI Ingestion Service + GPS Stream Simulator
Emits realistic shipment position events to Kafka/Redis.
In demo mode: simulates 2,847 trucks moving across the US.
"""
import os, json, time, random, math, asyncio
from dotenv import load_dotenv
import redis.asyncio as aioredis

load_dotenv()

SHIPMENT_COUNT = int(os.getenv("SIMULATOR_SHIPMENT_COUNT", 100))
EMIT_INTERVAL  = float(os.getenv("SIMULATOR_EMIT_INTERVAL_SEC", 5))
DISRUPTION_PROB= float(os.getenv("SIMULATOR_DISRUPTION_PROB", 0.001))

US_CORRIDORS = [
    {"from": "HUB_SEA", "to": "HUB_CHI",  "lat_range": (41, 47), "lon_range": (-122, -88)},
    {"from": "HUB_LAX", "to": "HUB_HOU",  "lat_range": (29, 34), "lon_range": (-118, -95)},
    {"from": "HUB_CHI", "to": "HUB_NYC",  "lat_range": (40, 42), "lon_range": (-87, -74)},
    {"from": "HUB_DAL", "to": "HUB_MIA",  "lat_range": (25, 33), "lon_range": (-97, -80)},
    {"from": "HUB_HOU", "to": "PORT_HOU", "lat_range": (29, 30), "lon_range": (-96, -95)},
    {"from": "HUB_ATL", "to": "HUB_NYC",  "lat_range": (33, 41), "lon_range": (-84, -74)},
    {"from": "HUB_MEM", "to": "HUB_CHI",  "lat_range": (35, 42), "lon_range": (-90, -87)},
    {"from": "HUB_DEN", "to": "HUB_DAL",  "lat_range": (32, 40), "lon_range": (-105, -97)},
]

CARRIERS = ["FedEx Freight", "UPS Supply Chain", "XPO Logistics", "Old Dominion", "Knight-Swift"]


class ShipmentSimulator:
    def __init__(self, shipment_id: str, corridor: dict):
        self.shipment_id = shipment_id
        self.corridor    = corridor
        self.lat = random.uniform(*corridor["lat_range"])
        self.lon = random.uniform(*corridor["lon_range"])
        self.speed       = random.uniform(55, 75)
        self.carrier     = random.choice(CARRIERS)
        self.risk_score  = random.uniform(0.05, 0.25)
        self.status      = "on_track"
        self.heading     = random.uniform(0, 360)

    def step(self) -> dict:
        # Move toward destination
        lat_range = self.corridor["lat_range"]
        lon_range = self.corridor["lon_range"]
        target_lat = (lat_range[0] + lat_range[1]) / 2 + random.gauss(0, 0.05)
        target_lon = lon_range[1]

        self.lat += (target_lat - self.lat) * 0.01 + random.gauss(0, 0.02)
        self.lon += (target_lon - self.lon) * 0.01 + random.gauss(0, 0.02)

        # Clamp to plausible US coords
        self.lat = max(24, min(49, self.lat))
        self.lon = max(-125, min(-66, self.lon))

        # Random speed deviation
        self.speed = max(0, self.speed + random.gauss(0, 3))
        speed_deviation = (self.speed - 65) / 65

        return {
            "shipment_id":    self.shipment_id,
            "carrier":        self.carrier,
            "lat":            round(self.lat, 5),
            "lon":            round(self.lon, 5),
            "speed_kmh":      round(self.speed, 1),
            "heading_deg":    round(self.heading, 1),
            "speed_deviation":round(speed_deviation, 3),
            "risk_score":     round(self.risk_score, 3),
            "status":         self.status,
            "from_hub":       self.corridor["from"],
            "to_hub":         self.corridor["to"],
            "timestamp":      time.time(),
        }


async def run_simulator():
    redis_client = aioredis.from_url(
        f"redis://{os.getenv('REDIS_HOST','localhost')}:{os.getenv('REDIS_PORT',6379)}",
        decode_responses=True
    )

    print(f"Initializing {SHIPMENT_COUNT} shipment simulators...")
    shipments = [
        ShipmentSimulator(
            f"SHP-{8000 + i}",
            US_CORRIDORS[i % len(US_CORRIDORS)]
        )
        for i in range(SHIPMENT_COUNT)
    ]

    # Register shipments in Redis
    pipe = redis_client.pipeline()
    for s in shipments:
        pipe.hset(f"shipment:{s.shipment_id}", mapping={
            "shipment_id": s.shipment_id,
            "carrier": s.carrier,
            "current_hub": s.corridor["from"],
            "destination": s.corridor["to"],
            "current_route": json.dumps([s.corridor["from"], s.corridor["to"]]),
            "current_route_cost": str(random.randint(500, 2000)),
            "optimization_weights": json.dumps({"cost": 0.4, "time": 0.3, "risk": 0.3}),
            "status": "on_track",
            "risk_score": str(s.risk_score),
        })
        pipe.sadd(f"shipments_via:{s.corridor['from']}", s.shipment_id)
        pipe.sadd(f"shipments_via:{s.corridor['to']}", s.shipment_id)
    await pipe.execute()
    print(f"Registered {SHIPMENT_COUNT} shipments in Redis.")
    print(f"Emitting GPS events every {EMIT_INTERVAL}s. Press Ctrl+C to stop.\n")

    tick = 0
    while True:
        tick += 1
        pipe = redis_client.pipeline()
        for s in shipments:
            event = s.step()
            # Update position in Redis
            pipe.hset(f"shipment:{s.shipment_id}", mapping={
                "lat": event["lat"],
                "lon": event["lon"],
                "speed_kmh": event["speed_kmh"],
                "risk_score": event["risk_score"],
                "status": event["status"],
            })
            # Publish to stream
            pipe.xadd("stream:gps-events", {
                "data": json.dumps(event)
            }, maxlen=10000)
        await pipe.execute()

        # Occasionally emit a mock disruption for demo
        if random.random() < DISRUPTION_PROB:
            disruption = {
                "type": random.choice(["weather_alert", "traffic_incident"]),
                "affected_nodes": [random.choice(["HUB_HOU", "HUB_DAL", "HUB_ATL"])],
                "severity": round(random.uniform(0.5, 0.95), 2),
                "duration_hours": random.randint(2, 12),
            }
            await redis_client.xadd("stream:disruption-events",
                                    {"data": json.dumps(disruption)}, maxlen=1000)
            print(f"Disruption emitted: {disruption}")

        if tick % 10 == 0:
            print(f"Tick {tick}: emitted {SHIPMENT_COUNT} GPS events")

        await asyncio.sleep(EMIT_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_simulator())
