import asyncio
import random
import time
from datetime import datetime, timezone
from db import bulk_insert_logs

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

_current_scenario  = "normal"
_scenario_intensity = 1.0
_scenario_start_time = time.time()

def set_scenario(scenario: str, intensity: float = 1.0):
    global _current_scenario, _scenario_intensity, _scenario_start_time
    _current_scenario   = scenario
    _scenario_intensity = intensity
    _scenario_start_time = time.time()

def get_current_scenario():
    return _current_scenario

def _generate_log():
    scenario = SCENARIOS[_current_scenario]
    endpoint, method, service = random.choices(ENDPOINTS, weights=ENDPOINT_WEIGHTS, k=1)[0]

    affected = "affected_endpoints" not in scenario or endpoint in scenario["affected_endpoints"]
    effective_error_rate = scenario["error_rate"] * _scenario_intensity if affected else 0.005

    # Progressive memory leak: latency climbs over 90 seconds then plateaus
    if _current_scenario == "memory_leak" and affected:
        elapsed      = time.time() - _scenario_start_time
        growth       = min(4.0, 1.0 + (elapsed / 45.0))  # 1x → 4x over 45s
        base_latency = scenario["base_latency"] * growth
        latency_std  = scenario["latency_std"] * growth
    else:
        base_latency = scenario["base_latency"] if affected else 72
        latency_std  = scenario["latency_std"]  if affected else 18

    latency  = max(8, random.gauss(base_latency, latency_std))
    is_error = random.random() < effective_error_rate

    if is_error:
        status    = scenario.get("status_override", random.choice([500, 502, 503, 504]))
        error_msg = random.choice(scenario.get("error_messages", ["Internal Server Error"]))
    else:
        status    = random.choices([200, 201, 204], weights=[80, 15, 5])[0]
        error_msg = None

    return {
        "timestamp":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "endpoint":      endpoint,
        "method":        method,
        "status_code":   status,
        "latency_ms":    round(latency, 2),
        "error_message": error_msg,
        "service":       service,
        "user_id":       f"usr_{random.randint(10000, 99999)}",
        "metadata": {
            "scenario": _current_scenario,
            "region":   random.choices(
                ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
                weights=[45, 25, 20, 10]
            )[0],
            "version":  "3.1.2",
            "trace_id": f"{random.randint(0, 0xFFFFFF):06x}{random.randint(0, 0xFFFFFF):06x}",
        },
    }

async def run_generator(broadcast_fn, rps: int = 30):
    """Generate logs at ~rps/second with realistic traffic burst patterns."""
    tick = 0
    while True:
        tick += 1
        # Simulate realistic burst: +/-20% jitter per second
        jitter = random.randint(-rps // 5, rps // 5)
        # Occasional traffic spike (every ~30s) to simulate real usage patterns
        if tick % 30 == 0:
            jitter = rps // 3
        count = max(4, rps + jitter)

        batch = [_generate_log() for _ in range(count)]
        await bulk_insert_logs(batch)
        # Slim payload for WS broadcast — strip metadata/user_id (never rendered)
        slim = [{
            "timestamp":   l["timestamp"],
            "endpoint":    l["endpoint"],
            "method":      l["method"],
            "status_code": l["status_code"],
            "latency_ms":  l["latency_ms"],
            "error_message": l.get("error_message"),
        } for l in batch]
        await broadcast_fn({"type": "logs", "data": slim})
        await asyncio.sleep(1)
