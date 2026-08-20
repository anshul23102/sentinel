import asyncio
import math
import random
import time
from datetime import datetime, timezone
from db import bulk_insert_logs
import state

# Simulated time compression: a full "day" cycles every 3 real minutes and a
# full "week" every 7 simulated days (21 real minutes). A genuine 24-hour
# cycle can't be demonstrated or verified within a working session, so this
# runs on an accelerated, clearly-labeled clock instead of silently pretending
# to be real time — daily/weekly seasonality is then something you can
# actually watch happen and test against, not something asserted on faith.
SIM_DAY_SECONDS  = 180
SIM_WEEK_DAYS    = 7
BUCKETS_PER_DAY  = 12   # shared with main.py's periodic bucket recording and the seasonal Holt-Winters fit

def seasonal_multiplier() -> tuple[float, float]:
    """(traffic_multiplier, latency_multiplier) for the current point in the
    simulated day/week cycle. Traffic follows a daily peak/trough plus a
    milder weekly dip; latency rises slightly with load — the same real-world
    correlation between traffic volume and response time."""
    now = time.time()
    day_phase  = (now % SIM_DAY_SECONDS) / SIM_DAY_SECONDS * 2 * math.pi
    week_phase = (now % (SIM_DAY_SECONDS * SIM_WEEK_DAYS)) / (SIM_DAY_SECONDS * SIM_WEEK_DAYS) * 2 * math.pi

    daily  = 1.0 + 0.55 * math.sin(day_phase - math.pi / 2)
    weekly = 1.0 + 0.20 * math.sin(week_phase - math.pi / 2)
    traffic_mult  = max(0.25, daily * weekly)
    latency_mult  = 1.0 + 0.12 * (traffic_mult - 1.0)
    return traffic_mult, latency_mult

# Endpoints with REALISTIC traffic weights matching e-commerce patterns:
# browse/search dominate, checkout is rare but critical
ENDPOINTS = [
    ("/api/products",      "GET",  "catalog-service"),
    ("/api/search",        "GET",  "search-service"),
    ("/api/inventory",     "GET",  "inventory-service"),
    ("/api/cart",          "POST", "cart-service"),
    ("/api/auth/login",    "POST", "auth-service"),
    ("/api/orders",        "GET",  "order-service"),
    ("/api/checkout",      "POST", "payment-service"),
    ("/api/users/profile", "GET",  "user-service"),
]

# Traffic weights: product browsing is 25%, search 22%, rare profile visits 3%
ENDPOINT_WEIGHTS = [25, 22, 15, 14, 10, 8, 4, 2]

SCENARIOS = {
    "normal": {
        "error_rate":    0.005,
        "base_latency":  72,
        "latency_std":   18,
        "description":   "Normal healthy traffic",
        "error_messages": [
            "Request validation failed: missing required field",
            "Resource temporarily unavailable — retrying",
        ],
    },
    "db_slowdown": {
        "error_rate":    0.15,
        "base_latency":  850,
        "latency_std":   220,
        "description":   "Database connection pool exhaustion causing cascading timeouts",
        "affected_endpoints": ["/api/checkout", "/api/orders", "/api/cart"],
        "error_messages": [
            "FATAL: remaining connection slots reserved for replication",
            "ERROR: deadlock detected — transaction rolled back on table 'orders'",
            "Connection pool timeout after 30000ms: no available connections",
            "HikariPool-1 — Connection is not available, request timed out after 30000ms",
            "ERROR: canceling statement due to conflict with recovery",
        ],
    },
    "memory_leak": {
        "error_rate":    0.06,
        "base_latency":  300,
        "latency_std":   80,
        "description":   "Memory leak causing gradual heap pressure and GC pauses",
        "affected_endpoints": ["/api/search", "/api/products"],
        "error_messages": [
            "Out of memory: Kill process — Killed process (java) total-vm:4096MB",
            "java.lang.OutOfMemoryError: GC overhead limit exceeded",
            "java.lang.OutOfMemoryError: Java heap space",
            "ENOMEM: cannot allocate memory — search index cache eviction failed",
        ],
    },
    "rate_limit_cascade": {
        "error_rate":    0.38,
        "base_latency":  115,
        "latency_std":   25,
        "description":   "Upstream rate limiting causing 429 cascade across authentication layer",
        "affected_endpoints": ["/api/auth/login", "/api/users/profile"],
        "error_messages": [
            "Rate limit exceeded: 429 from upstream OAuth provider — retry after 60s",
            "Too Many Requests: identity service throttling at 100 req/min",
            "Auth0: API request limit reached for your subscription",
            "Downstream: 429 User rate limit exceeded",
        ],
        "status_override": 429,
    },
    "network_partition": {
        "error_rate":    0.65,
        "base_latency":  4800,
        "latency_std":   900,
        "description":   "Network partition between services causing timeouts and split-brain",
        "affected_endpoints": ["/api/checkout", "/api/inventory"],
        "error_messages": [
            "Connection timeout: inventory-service:8080 unreachable after 5000ms",
            "ECONNREFUSED: connect ECONNREFUSED 10.0.1.24:8080",
            "Circuit breaker OPEN: inventory-service — 10 failures in last 60s",
            "Consul health check failed: inventory-service deregistered",
            "gRPC: DEADLINE_EXCEEDED — upstream did not respond within 4800ms",
        ],
    },
}

async def set_scenario(sid: str, scenario: str, intensity: float = 1.0):
    await state.set_scenario(sid, scenario, intensity, time.time())

async def get_current_scenario(sid: str) -> str:
    return (await state.get_scenario(sid))["current"]

def _generate_log(sid: str, scenario_state: dict, latency_mult: float = 1.0):
    current_scenario_name = scenario_state["current"]
    scenario     = SCENARIOS[current_scenario_name]
    intensity    = scenario_state["intensity"]
    start_time   = scenario_state["start_time"]
    endpoint, method, service = random.choices(ENDPOINTS, weights=ENDPOINT_WEIGHTS, k=1)[0]

    affected = "affected_endpoints" not in scenario or endpoint in scenario["affected_endpoints"]
    is_failure_hit = current_scenario_name != "normal" and affected
    effective_error_rate = scenario["error_rate"] * intensity if affected else 0.005

    # Progressive memory leak: latency climbs over 90 seconds then plateaus
    if current_scenario_name == "memory_leak" and affected:
        elapsed      = time.time() - start_time
        growth       = min(4.0, 1.0 + (elapsed / 45.0))  # 1x → 4x over 45s
        base_latency = scenario["base_latency"] * growth
        latency_std  = scenario["latency_std"] * growth
    elif is_failure_hit:
        # An injected failure stays crisply detectable regardless of
        # simulated time of day — seasonal modulation only touches the
        # healthy baseline below, never the failure magnitude itself.
        base_latency = scenario["base_latency"]
        latency_std  = scenario["latency_std"]
    else:
        base_latency = 72 * latency_mult
        latency_std  = 18

    latency  = max(8, random.gauss(base_latency, latency_std))
    is_error = random.random() < effective_error_rate

    if is_error:
        status    = scenario.get("status_override", random.choice([500, 502, 503, 504]))
        error_msg = random.choice(scenario.get("error_messages", ["Internal Server Error"]))
    else:
        status    = random.choices([200, 201, 204], weights=[80, 15, 5])[0]
        error_msg = None

    return {
        "session_id":    sid,
        "timestamp":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "endpoint":      endpoint,
        "method":        method,
        "status_code":   status,
        "latency_ms":    round(latency, 2),
        "error_message": error_msg,
        "service":       service,
        "user_id":       f"usr_{random.randint(10000, 99999)}",
        "metadata": {
            "scenario": current_scenario_name,
            "region":   random.choices(
                ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
                weights=[45, 25, 20, 10]
            )[0],
            "version":  "3.1.2",
            "trace_id": f"{random.randint(0, 0xFFFFFF):06x}{random.randint(0, 0xFFFFFF):06x}",
        },
    }

async def run_generator(sid: str, broadcast_fn, rps: int = 30):
    """Generate logs at ~rps/second with realistic traffic burst patterns,
    for one session's isolated simulated world. Runs until cancelled by the
    session manager when this session goes idle."""
    tick = 0
    while True:
        tick += 1
        # Simulate realistic burst: +/-20% jitter per second
        jitter = random.randint(-rps // 5, rps // 5)
        # Occasional traffic spike (every ~30s) to simulate real usage patterns
        if tick % 30 == 0:
            jitter = rps // 3
        traffic_mult, latency_mult = seasonal_multiplier()
        count = max(4, round((rps + jitter) * traffic_mult))

        # Read scenario state from Redis once per tick, not once per log —
        # keeps the hot path from hammering Redis dozens of times a second.
        scenario_state = await state.get_scenario(sid)
        batch = [_generate_log(sid, scenario_state, latency_mult) for _ in range(count)]
        await bulk_insert_logs(sid, batch)
        # Slim payload for WS broadcast — strip metadata/user_id (never rendered)
        slim = [{
            "timestamp":   log["timestamp"],
            "endpoint":    log["endpoint"],
            "method":      log["method"],
            "status_code": log["status_code"],
            "latency_ms":  log["latency_ms"],
            "error_message": log.get("error_message"),
        } for log in batch]
        await broadcast_fn({"type": "logs", "data": slim})
        await asyncio.sleep(1)
