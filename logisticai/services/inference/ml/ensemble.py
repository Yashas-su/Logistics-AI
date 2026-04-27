import math
import random
import numpy as np


class DelayEnsemble:
    """
    Demo ensemble predictor.
    In production: loads XGBoost + PyTorch LSTM from Vertex AI or local model files.
    In demo mode: uses a hand-tuned heuristic that mimics the real model's behavior.
    """

    def __init__(self):
        self.loaded = False
        self.model_version = "demo_v1"

    def load_demo(self):
        """Initialize demo model — no external dependencies needed."""
        random.seed(42)
        self.loaded = True
        print("Demo ensemble model loaded (heuristic mode).")

    def predict(self, features: dict) -> dict:
        if not self.loaded:
            raise RuntimeError("Model not loaded. Call load_demo() first.")

        speed_dev    = features.get("speed_deviation_pct", 0.0)
        precip       = features.get("precip_intensity", 0.0)
        congestion   = features.get("congestion_level", 0.2)
        hist_delay   = features.get("segment_historical_delay_p50", 12.0)
        carrier_ota  = features.get("carrier_on_time_rate_30d", 0.88)
        port_wait    = features.get("port_wait_hours_rolling_7d", 1.5)
        dow          = features.get("day_of_week", 1)
        hour         = features.get("hour_of_day", 12)
        customs_risk = features.get("customs_clearance_risk_score", 0.1)
        veh_age      = features.get("vehicle_age_days", 365)
        route_risk   = features.get("route_risk_composite", 0.15)

        # XGBoost-style tabular prediction
        base = hist_delay
        base *= 1 + max(0, -speed_dev) * 0.4
        base *= 1 + precip * 1.8
        base *= 1 + congestion * 1.2
        base *= 1 + (1 - carrier_ota) * 0.6
        base *= 1 + port_wait * 0.08
        base *= 1 + customs_risk * 0.5
        base *= 1 + (veh_age / 3650) * 0.1
        base *= 1 + route_risk * 0.4

        # Day/hour adjustment
        if dow in (5, 6):
            base *= 0.85
        if 7 <= hour <= 9 or 16 <= hour <= 19:
            base *= 1.15

        # LSTM component (temporal drift simulation)
        lstm_component = base * (1 + random.gauss(0, 0.08))

        # Blend
        alpha = 0.6
        blended = alpha * base + (1 - alpha) * lstm_component

        # MC Dropout simulation — 200 samples
        samples = [blended * (1 + random.gauss(0, 0.12)) for _ in range(200)]
        arr = sorted(samples)

        p10 = max(0, arr[20])
        p50 = max(0, arr[100])
        p90 = max(0, arr[180])
        std_dev = float(np.std(arr))

        risk = min(1.0, p50 / 240.0)

        return {
            "delay_p10_minutes": round(p10, 1),
            "delay_p50_minutes": round(p50, 1),
            "delay_p90_minutes": round(p90, 1),
            "risk_score": round(risk, 3),
            "uncertainty": round(std_dev / max(p50, 1), 3),
            "source": "ensemble_model",
            "model_version": self.model_version,
        }
