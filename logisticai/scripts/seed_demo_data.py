#!/usr/bin/env python3
"""
Seed demo shipment data into Redis and Postgres.
Run: python scripts/seed_demo_data.py
"""
import os, sys, json, random, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

import redis.asyncio as aioredis

CORRIDORS = [
    {"from": "HUB_CHI", "to": "HUB_HOU",  "lat": (35, 42), "lon": (-97, -88)},
    {"from": "HUB_DAL", "to": "HUB_MIA",  "lat": (25, 33), "lon": (-97, -80)},
    {"from": "HUB_LAX", "to": "HUB_HOU",  "lat": (29, 34), "lon": (-118, -95)},
    {"from": "HUB_SEA", "to": "HUB_CHI",  "lat": (41, 48), "lon": (-122, -88)},
    {"from": "HUB_NYC", "to": "HUB_ATL",  "lat": (33, 41), "lon": (-84, -74)},
    {"from": "HUB_MEM", "to": "PORT_BMT", "lat": (29, 36), "lon": (-94, -89)},
    {"from": "HUB_DEN", "to": "HUB_DAL",  "lat": (32, 40), "lon": (-105, -97)},
    {"from": "HUB_ATL", "to": "PORT_MSY", "lat": (29, 34), "lon": (-90, -84)},
]

CARRIERS = ["FedEx Freight", "UPS Supply Chain", "XPO Logistics", "Old Dominion", "Knight-Swift"]

async def seed():
    redis_url = f"redis://{os.getenv('REDIS_HOST','localhost')}:{os.getenv('REDIS_PORT',6379)}"
    r = aioredis.from_url(redis_url, decode_responses=True)

    print("Connecting to Redis...")
    await r.ping()
    print("Redis connected. Seeding 2,847 shipments...")

    pipe = r.pipeline()
    for i in range(2847):
        corridor = CORRIDORS[i % len(CORRIDORS)]
        lat = corridor["lat"][0] + random.random() * (corridor["lat"][1] - corridor["lat"][0])
        lon = corridor["lon"][0] + random.random() * (corridor["lon"][1] - corridor["lon"][0])
        risk = round(0.05 + random.random() * 0.25, 4)
        sid = f"SHP-{8000 + i}"

        pipe.hset(f"shipment:{sid}", mapping={
            "shipment_id":           sid,
            "carrier":               CARRIERS[i % len(CARRIERS)],
            "current_hub":           corridor["from"],
            "destination":           corridor["to"],
            "current_route":         json.dumps([corridor["from"], corridor["to"]]),
            "current_route_cost":    str(round(random.uniform(500, 2500), 2)),
            "optimization_weights":  json.dumps({"cost": 0.4, "time": 0.3, "risk": 0.3}),
            "status":                "on_track",
            "risk_score":            str(risk),
            "lat":                   str(round(lat, 5)),
            "lon":                   str(round(lon, 5)),
        })

        # Register in route index
        pipe.sadd(f"shipments_via:{corridor['from']}", sid)
        pipe.sadd(f"shipments_via:{corridor['to']}", sid)

        # Batch every 200
        if i % 200 == 0:
            await pipe.execute()
            pipe = r.pipeline()
            print(f"  Seeded {i+1}/2847...")

    await pipe.execute()
    total = await r.dbsize()
    print(f"\nDone! Redis now has {total} keys.")
    print("Demo shipments available at shipment:SHP-8000 through shipment:SHP-10846")
    await r.aclose()

if __name__ == "__main__":
    asyncio.run(seed())
