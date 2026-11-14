"""Offline evaluation of the real detector against the built-in simulator.

Answers two questions with measurements instead of claims:

  1. FALSE ALERTS: on healthy traffic, how often does the detector raise an
     anomaly it should not have? (reported per simulated hour)
  2. TIME TO DETECT: after a failure scenario starts, how many seconds until
     the detector raises an anomaly on an endpoint the scenario actually
     affects? (and what fraction of trials detect it at all)

It drives the production code path (anomaly_detector.process_log_batch and
run_anomaly_scan, against real Postgres and Redis) but on a SIMULATED clock,
so an hour of traffic takes seconds instead of an hour: time.time() inside
state.py (window eviction) and log_generator.py (seasonality, scenario age)
is replaced with the simulated clock. Nothing else is mocked.

Usage (from backend/, with Postgres and Redis running):

    python scripts/evaluate_detection.py --trials 8 --normal-minutes 30

It writes to the test database (sentinel_test) and Redis DB 1, never to the
demo's data, and removes every key and row it creates.
"""
import argparse
import asyncio
import json
import os
import random
import statistics
import sys
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql://localhost/sentinel_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("GROQ_API_KEY", "")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db  # noqa: E402
import log_generator  # noqa: E402
import state  # noqa: E402
from anomaly_detector import process_log_batch, run_anomaly_scan  # noqa: E402

START_EPOCH = 1_800_000_000.0  # arbitrary fixed start so runs are comparable
REAL_ANOMALY_TYPES = {"latency_spike", "error_surge", "changepoint", "cascade_failure"}


class SimClock:
    """Stands in for the `time` module inside state.py and log_generator.py."""

    def __init__(self, start: float):
        self.now = start

    def time(self) -> float:
        return self.now

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float = 1.0) -> None:
        self.now += seconds


def _make_batch(sid: str, scenario_state: dict, rps: int, tick: int) -> list[dict]:
    """Same batch-size logic as log_generator.run_generator, minus the sleep."""
    jitter = random.randint(-rps // 5, rps // 5)
    if tick % 30 == 0:
        jitter = rps // 3
    traffic_mult, latency_mult = log_generator.seasonal_multiplier()
    count = max(4, round((rps + jitter) * traffic_mult))
    return [log_generator._generate_log(sid, scenario_state, latency_mult) for _ in range(count)]


async def _tick(sid: str, clock: SimClock, scenario_state: dict, rps: int, tick: int) -> list[dict]:
    batch = _make_batch(sid, scenario_state, rps, tick)
    found = await process_log_batch(sid, batch)
    if tick % 5 == 0:  # periodic_scan runs every 5 s in production
        cascades: list[dict] = []

        async def collect(message: dict):
            cascades.append(message["data"])
        await run_anomaly_scan(sid, collect)
        found = found + cascades
    clock.advance(1.0)
    return found


async def _cleanup(sid: str) -> None:
    await db.delete_session_data(sid)
    c = state.get_client()
    keys = await c.keys(f"sentinel:{sid}:*")
    if keys:
        await c.delete(*keys)


async def run_normal_trial(seed: int, minutes: int, rps: int, warmup: int) -> dict:
    random.seed(seed)
    sid = f"eval-normal-{uuid.uuid4()}"
    clock = SimClock(START_EPOCH + seed * 10_000)
    state.time = log_generator.time = clock
    scenario_state = {"current": "normal", "intensity": 1.0, "start_time": clock.now}
    try:
        for t in range(warmup):
            await _tick(sid, clock, scenario_state, rps, t)
        alerts: list[dict] = []
        for t in range(minutes * 60):
            alerts.extend(await _tick(sid, clock, scenario_state, rps, warmup + t))
        return {"seconds": minutes * 60, "alerts": [a["anomaly_type"] for a in alerts]}
    finally:
        await _cleanup(sid)


async def run_scenario_trial(name: str, seed: int, rps: int, warmup: int, window: int) -> dict:
    random.seed(seed)
    sid = f"eval-{name}-{uuid.uuid4()}"
    clock = SimClock(START_EPOCH + seed * 10_000)
    state.time = log_generator.time = clock
    healthy = {"current": "normal", "intensity": 1.0, "start_time": clock.now}
    affected = set(log_generator.SCENARIOS[name].get("affected_endpoints", []))
    try:
        for t in range(warmup):
            await _tick(sid, clock, healthy, rps, t)
        failing = {"current": name, "intensity": 1.0, "start_time": clock.now}
        for t in range(window):
            found = await _tick(sid, clock, failing, rps, warmup + t)
            hits = [
                a for a in found
                if a["anomaly_type"] in REAL_ANOMALY_TYPES
                and (a["endpoint"] in affected or a["anomaly_type"] == "cascade_failure")
            ]
            if hits:
                return {"detected": True, "seconds": t + 1, "first_type": hits[0]["anomaly_type"],
                        "types": sorted({a["anomaly_type"] for a in hits})}
        return {"detected": False, "seconds": None, "first_type": None, "types": []}
    finally:
        await _cleanup(sid)


def _pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--trials", type=int, default=8, help="trials per failure scenario")
    parser.add_argument("--normal-trials", type=int, default=3, help="trials of healthy-only traffic")
    parser.add_argument("--normal-minutes", type=int, default=30, help="simulated minutes of healthy traffic per trial")
    parser.add_argument("--rps", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=120, help="healthy seconds before measuring or injecting")
    parser.add_argument("--window", type=int, default=90, help="seconds allowed to detect after injection")
    parser.add_argument("--json", action="store_true", help="print machine-readable results only")
    args = parser.parse_args()

    await db.init_db()
    results: dict = {"config": vars(args), "normal": {}, "scenarios": {}}

    normal = [await run_normal_trial(100 + i, args.normal_minutes, args.rps, args.warmup)
              for i in range(args.normal_trials)]
    total_seconds = sum(t["seconds"] for t in normal)
    all_alerts = [a for t in normal for a in t["alerts"]]
    by_type: dict[str, int] = {}
    for a in all_alerts:
        by_type[a] = by_type.get(a, 0) + 1
    hours = total_seconds / 3600
    results["normal"] = {
        "simulated_hours": round(hours, 2),
        "false_alerts": len(all_alerts),
        "false_alerts_per_hour": round(len(all_alerts) / hours, 2) if hours else None,
        "by_type": by_type,
    }

    for name in ("db_slowdown", "memory_leak", "rate_limit_cascade", "network_partition"):
        trials = [await run_scenario_trial(name, 200 + i, args.rps, args.warmup, args.window)
                  for i in range(args.trials)]
        times = [t["seconds"] for t in trials if t["detected"]]
        first: dict[str, int] = {}
        for t in trials:
            if t["first_type"]:
                first[t["first_type"]] = first.get(t["first_type"], 0) + 1
        results["scenarios"][name] = {
            "trials": len(trials),
            "detected": len(times),
            "detection_rate": round(len(times) / len(trials), 2),
            "median_seconds_to_detect": statistics.median(times) if times else None,
            "p90_seconds_to_detect": _pct(times, 0.9) if times else None,
            "max_seconds_to_detect": max(times) if times else None,
            "first_detector": first,
        }

    if args.json:
        print(json.dumps(results, indent=2))
        return
    n = results["normal"]
    print(f"\nHEALTHY TRAFFIC: {n['simulated_hours']} simulated hours, "
          f"{n['false_alerts']} false alerts = {n['false_alerts_per_hour']} per hour  {n['by_type']}")
    print(f"\n{'scenario':<20}{'detected':>10}{'median s':>10}{'p90 s':>8}{'max s':>8}   first detector")
    for name, r in results["scenarios"].items():
        print(f"{name:<20}{str(r['detected']) + '/' + str(r['trials']):>10}"
              f"{str(r['median_seconds_to_detect']):>10}{str(r['p90_seconds_to_detect']):>8}"
              f"{str(r['max_seconds_to_detect']):>8}   {r['first_detector']}")


if __name__ == "__main__":
    asyncio.run(main())
