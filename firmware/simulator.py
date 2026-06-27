"""
Smart Agri-Monitor - ESP32 Multi-Node Telemetry Simulator
==========================================================
Simulates realistic sensor readings for multiple farm nodes, replicating
the edge processing behaviour of the physical ESP32 firmware:
  • Moving-average buffer (window = 10) applied locally before transmission
  • Adaptive interval: anomalies sent immediately, normals every 5 s (demo speed)
  • Diurnal temperature / humidity cycle
  • Random anomaly injection (~5 % chance per cycle)

Usage:
    python simulator.py [--url http://127.0.0.1:8000] [--interval 5]

Register a farm + devices via the API first, then paste their api_keys below.
"""

import argparse
import math
import random
import time
import datetime
import json
try:
    import requests
except ImportError:
    raise SystemExit("requests not installed — run: pip install requests")

# ── Configuration ──────────────────────────────────────────────────────────────

DEVICE_NODES = [
    {"name": "salam cola",             "api_key": "node-64acb5461493"},
    {"name": "solana",                 "api_key": "node-9f88130f2d7e"},
]

WINDOW_SIZE = 10   # moving-average window — mirrors firmware constant

# ── Physics Helpers ────────────────────────────────────────────────────────────

def diurnal_temp(base: float = 26.0, amplitude: float = 8.0) -> float:
    """Return temperature following a realistic diurnal sine curve (peaks at 14:00)."""
    hour = datetime.datetime.now().hour + datetime.datetime.now().minute / 60
    return base + amplitude * math.sin((hour - 8) * math.pi / 12)

def diurnal_humidity(base: float = 60.0, amplitude: float = 20.0) -> float:
    """Humidity is inversely related to temperature (rises at night)."""
    hour = datetime.datetime.now().hour + datetime.datetime.now().minute / 60
    return base - amplitude * math.sin((hour - 8) * math.pi / 12)

def moving_average(buf: list) -> float:
    return sum(buf) / len(buf)

# ── Node Simulator Class ───────────────────────────────────────────────────────

class SensorNode:
    def __init__(self, name: str, api_key: str):
        self.name    = name
        self.api_key = api_key

        # Soil state (persists across readings so watering effects are visible)
        self.soil_moisture = random.uniform(40.0, 70.0)
        self.ph            = random.uniform(6.0, 7.2)

        # Ring buffers (edge moving-average)
        self.buf_moisture: list[float] = []
        self.buf_ph:       list[float] = []
        self.buf_temp:     list[float] = []
        self.buf_humidity: list[float] = []

    def _raw_readings(self) -> dict:
        """Generate one raw sensor sample with natural physics applied."""
        # Soil moisture slowly drops due to evapotranspiration
        et_loss = random.uniform(0.05, 0.3)
        self.soil_moisture = max(5.0, self.soil_moisture - et_loss)

        # pH drifts slightly
        self.ph += random.uniform(-0.02, 0.02)
        self.ph = round(max(4.5, min(8.5, self.ph)), 2)

        return {
            "soil_moisture": round(self.soil_moisture + random.gauss(0, 0.5), 2),
            "ph":            round(self.ph + random.gauss(0, 0.05), 2),
            "temperature":   round(diurnal_temp()    + random.gauss(0, 0.3), 2),
            "humidity":      round(diurnal_humidity() + random.gauss(0, 1.0), 2),
        }

    def _inject_anomaly(self, reading: dict) -> dict:
        """Occasionally inject a critical reading to test alert pipeline."""
        anomaly_type = random.choice(["drought", "heat", "acid"])
        if anomaly_type == "drought":
            reading["soil_moisture"] = round(random.uniform(5.0, 13.0), 2)
            print(f"  ⚡ [{self.name}] Anomaly injected: CRITICAL DROUGHT (moisture={reading['soil_moisture']}%)")
        elif anomaly_type == "heat":
            reading["temperature"] = round(random.uniform(46.0, 52.0), 2)
            print(f"  ⚡ [{self.name}] Anomaly injected: EXTREME HEAT (temp={reading['temperature']}°C)")
        else:
            reading["ph"] = round(random.uniform(3.5, 4.2), 2)
            print(f"  ⚡ [{self.name}] Anomaly injected: ACIDIC SOIL (pH={reading['ph']})")
        return reading

    def sample_and_filter(self) -> dict:
        """
        Collect a raw reading, push to ring buffer, and return the moving average
        (or the raw reading if the buffer isn't full yet).
        """
        raw = self._raw_readings()

        # Occasionally inject an anomaly (~5 % chance)
        if random.random() < 0.05:
            raw = self._inject_anomaly(raw)

        # Update moving-average buffers
        for buf, key in [
            (self.buf_moisture, "soil_moisture"),
            (self.buf_ph,       "ph"),
            (self.buf_temp,     "temperature"),
            (self.buf_humidity, "humidity"),
        ]:
            buf.append(raw[key])
            if len(buf) > WINDOW_SIZE:
                buf.pop(0)

        if len(self.buf_moisture) < WINDOW_SIZE:
            return raw  # not enough data yet — send raw

        return {
            "soil_moisture": round(moving_average(self.buf_moisture), 3),
            "ph":            round(moving_average(self.buf_ph),       3),
            "temperature":   round(moving_average(self.buf_temp),     3),
            "humidity":      round(moving_average(self.buf_humidity), 3),
        }

    def simulate_watering(self):
        """Simulate a watering event — moisture recovers."""
        added = random.uniform(15.0, 30.0)
        self.soil_moisture = min(95.0, self.soil_moisture + added)
        print(f"  💧 [{self.name}] Watering event: moisture → {self.soil_moisture:.1f}%")

# ── Main Loop ─────────────────────────────────────────────────────────────────

def post_telemetry(url: str, api_key: str, data: dict) -> bool:
    try:
        resp = requests.post(
            f"{url}/api/telemetry",
            json=data,
            headers={"X-Api-Key": api_key},
            timeout=5,
        )
        return resp.status_code == 200
    except requests.exceptions.ConnectionError:
        return False

def main():
    parser = argparse.ArgumentParser(description="ESP32 Multi-Node Telemetry Simulator")
    parser.add_argument("--url",      default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--interval", type=float, default=5.0,         help="Seconds between transmissions")
    args = parser.parse_args()

    nodes = [SensorNode(n["name"], n["api_key"]) for n in DEVICE_NODES]
    watering_counter = {n.api_key: 0 for n in nodes}

    print(f"\n🌱  Smart Agri-Monitor Simulator  |  backend={args.url}  |  interval={args.interval}s")
    print(f"    Simulating {len(nodes)} sensor node(s). Press Ctrl-C to stop.\n")

    cycle = 0
    while True:
        cycle += 1
        print(f"── Cycle #{cycle}  [{datetime.datetime.now().strftime('%H:%M:%S')}] ──────────────────")

        for node in nodes:
            payload = node.sample_and_filter()
            ok = post_telemetry(args.url, node.api_key, payload)

            status_icon = "✅" if ok else "❌ (backend unreachable — check server)"
            print(
                f"  {status_icon} [{node.name}]  "
                f"moisture={payload['soil_moisture']:.1f}%  "
                f"pH={payload['ph']:.2f}  "
                f"temp={payload['temperature']:.1f}°C  "
                f"hum={payload['humidity']:.1f}%"
            )

            # Simulate a watering event every ~30 cycles per node
            watering_counter[node.api_key] += 1
            if watering_counter[node.api_key] >= 30:
                node.simulate_watering()
                watering_counter[node.api_key] = 0

        print()
        time.sleep(args.interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSimulator stopped.")
