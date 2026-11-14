// Generates realistic mock data when the backend is unavailable (Railway sleeping, etc.)

// Same endpoint names, and the same response shapes, as the real backend
// (see backend/log_generator.py and backend/anomaly_detector.py). Demo mode
// exists so the UI still works with no backend reachable, so it must speak the
// exact data contract the components read - a mock that drifts from the real
// shape renders blank cards and NaN values.
const ENDPOINTS = [
  '/api/products', '/api/search', '/api/inventory', '/api/cart',
  '/api/auth/login', '/api/orders', '/api/checkout', '/api/users/profile',
]
const SLO_TARGET = 0.99  // mirrors backend config.SLO_TARGET's default

const SERVICES = {
  '/api/auth/login':    { name: 'Auth',      deps: [] },
  '/api/checkout':      { name: 'Checkout',  deps: ['/api/auth/login', '/api/cart', '/api/orders'] },
  '/api/cart':          { name: 'Cart',      deps: ['/api/auth/login', '/api/inventory'] },
  '/api/products':      { name: 'Products',  deps: ['/api/inventory'] },
  '/api/search':        { name: 'Search',    deps: ['/api/products'] },
  '/api/inventory':     { name: 'Inventory', deps: [] },
  '/api/orders':        { name: 'Orders',    deps: ['/api/auth/login'] },
  '/api/users/profile': { name: 'Profile',   deps: ['/api/auth/login'] },
}

function rand(min, max) { return min + Math.random() * (max - min) }
function randInt(min, max) { return Math.floor(rand(min, max + 1)) }
function pick(arr) { return arr[randInt(0, arr.length - 1)] }

// Scenario profiles: [baseLatency, latencyJitter, errorRate]
const SCENARIO_PROFILES = {
  normal:        { lat: 80,  jitter: 25,  errRate: 0.005 },
  db_slowdown:   { lat: 480, jitter: 180, errRate: 0.18  },
  memory_leak:   { lat: 160, jitter: 80,  errRate: 0.06  },
  rate_limit_cascade:    { lat: 95,  jitter: 30,  errRate: 0.22  },
  network_partition: { lat: 210, jitter: 90,  errRate: 0.35  },
}

let _scenario = 'normal'
let _tick = 0

// Anomalies must carry a STABLE detected_at for the life of a scenario, like the
// real backend's do: the toast and feed code dedupe on detected_at + endpoint,
// so a timestamp regenerated every tick made the same fake incident look brand
// new each second and re-fired its toast forever.
let _scenarioStartedAt = Date.now()

export function setMockScenario(s) {
  _scenario = SCENARIO_PROFILES[s] ? s : 'normal'
  _scenarioStartedAt = Date.now()
}
export function getMockScenario()  { return _scenario }

export function generateLogBatch(batchSize = 30) {
  const profile = SCENARIO_PROFILES[_scenario]
  return Array.from({ length: batchSize }, (_, i) => {
    const ep = pick(ENDPOINTS)
    const latency = Math.max(8, Math.round(rand(
      profile.lat - profile.jitter,
      profile.lat + profile.jitter
    )))
    const isError = Math.random() < profile.errRate
    const status = isError
      ? (_scenario === 'rate_limit_cascade' ? 429 : _scenario === 'network_partition' ? 503 : pick([500, 502, 503]))
      : pick([200, 200, 200, 201, 200])
    return {
      id: Date.now() + i,
      endpoint: ep,
      method: ep.includes('checkout') || ep.includes('cart') ? pick(['POST', 'GET']) : 'GET',
      status_code: status,
      latency_ms: latency,
      timestamp: new Date().toISOString(),
      error_message: isError ? mockErrorMsg(_scenario, ep) : null,
    }
  })
}

function mockErrorMsg(scenario, ep) {
  const msgs = {
    db_slowdown:   ['connection pool exhausted', 'query timeout after 5000ms', 'deadlock detected'],
    memory_leak:   ['heap allocation failed', 'out of memory', 'GC pressure exceeded'],
    rate_limit_cascade:    ['rate limit exceeded: 429', 'too many requests', 'quota exhausted'],
    network_partition: ['ECONNREFUSED', 'network unreachable', 'timeout: upstream unavailable'],
  }
  return pick(msgs[scenario] || ['internal server error'])
}

// One endpoint's health entry in the real backend shape: latencies in
// `*_ms`, error_rate as a FRACTION (0.18 = 18%), plus the SLO fields.
function healthEntry(status, latencyMs, errorRate) {
  const allowed = 1 - SLO_TARGET
  return {
    status,
    avg_latency_ms: latencyMs,
    p95_latency_ms: Math.round(latencyMs * 1.6),
    error_rate: +errorRate.toFixed(3),
    uptime_pct: +((1 - errorRate) * 100).toFixed(1),
    error_budget_remaining_pct: +((1 - errorRate / allowed) * 100).toFixed(1),
    burn_rate: +(errorRate / allowed).toFixed(2),
    sample_size: randInt(180, 300),
  }
}

export function generateHealthSnapshot() {
  const profile = SCENARIO_PROFILES[_scenario]
  const snap = {}
  for (const ep of ENDPOINTS) {
    const baseOk = profile.errRate < 0.05
    const latency = Math.round(rand(profile.lat * 0.8, profile.lat * 1.3))
    const errPct  = +(rand(0, profile.errRate * 200)).toFixed(1)
    let status = 'healthy'
    if (errPct > 15 || latency > 400) status = 'critical'
    else if (errPct > 5  || latency > 200) status = 'degraded'

    // cascade: checkout/cart degrade when auth is critical
    if (!baseOk && (ep === '/api/checkout' || ep === '/api/cart') && _scenario !== 'normal') {
      status = 'critical'
    }
    snap[ep] = healthEntry(status, latency, errPct / 100)
  }
  return snap
}

export function generateAnomalies() {
  if (_scenario === 'normal') return []
  const chains = {
    db_slowdown:   [
      { service: '/api/auth/login', impact: 'Auth latency +340%' },
      { service: '/api/cart',       impact: 'Cart timeouts increasing' },
      { service: '/api/checkout',   impact: 'Checkout cascade failure' },
    ],
    memory_leak:   [
      { service: '/api/search',   impact: 'Search heap at 87%' },
      { service: '/api/products', impact: 'Products response degraded' },
    ],
    rate_limit_cascade:    [
      { service: '/api/auth/login',    impact: 'Auth returning 429' },
      { service: '/api/users/profile', impact: 'Profile calls blocked, no auth tokens' },
      { service: '/api/checkout',      impact: 'Checkout blocked, no auth tokens' },
    ],
    network_partition: [
      { service: '/api/inventory',  impact: 'Inventory unreachable' },
      { service: '/api/cart',       impact: '65% of cart reads failing' },
      { service: '/api/checkout',   impact: 'Checkout ECONNREFUSED' },
    ],
  }
  const chain = chains[_scenario] || []
  const isLatencyScenario = _scenario === 'db_slowdown' || _scenario === 'memory_leak'
  return chain.map((c, i) => ({
    id: 1000 + i,
    anomaly_type: isLatencyScenario ? 'latency_spike' : 'error_surge',
    severity: i === 0 ? 'critical' : 'warning',
    endpoint: c.service,
    description: c.impact,
    detected_at: new Date(_scenarioStartedAt - (chain.length - i) * 12000).toISOString(),
    // Same object shape the real detector emits (anomaly_detector._build_evidence_chain)
    root_cause_chain: chain.slice(0, i + 1).map((x, j) => ({
      step: j + 1,
      component: x.service,
      signal: x.impact,
      confidence: +Math.max(0.5, 0.96 - j * 0.11).toFixed(2),
    })),
    z_score: +rand(3.6, 8.5).toFixed(2),
  }))
}

export function generateAiAnalyses(anomalies) {
  const analyses = {}
  const texts = {
    db_slowdown:   'Connection pool exhausted on /api/auth (pool size: 10, demand: 28). Auth latency exceeded 500ms SLA, cascading timeouts to cart and checkout. Immediate actions: (1) increase pool size to 50 in DATABASE_POOL_SIZE env var, (2) add circuit breaker on cart → auth calls, (3) restart auth pod to clear stale connections.',
    memory_leak:   'Heap growing at ~12MB/min on search service. GC pause times now 200ms+, causing P95 latency to hit 620ms. Likely culprit: unbounded in-memory cache in product indexer. Actions: (1) cap cache size with LRU eviction, (2) restart search service now to recover heap, (3) add memory alert at 70% threshold.',
    rate_limit_cascade:    'Auth service rate limit hit — 429s flooding all downstream. Root cause: bot traffic spike from crawler subnet 54.23.x.x (1,200 rps). Actions: (1) block subnet in WAF, (2) raise auth rate limit to 2,000 rpm for internal services, (3) add Retry-After header to 429 responses.',
    network_partition: 'Network partition isolating inventory service — ECONNREFUSED from us-east-1b AZ. 65% of cart reads failing. Actions: (1) reroute inventory traffic to us-east-1a replica, (2) enable stale-read fallback for cart service, (3) file incident with infra team for AZ recovery.',
  }
  for (const a of anomalies) {
    analyses[a.id] = {
      anomaly_id:  a.id,
      analysis:    texts[_scenario] || 'Anomaly detected. Investigate recent deployments and traffic patterns.',
      analyzed_at: a.detected_at,
      model:       'openai/gpt-oss-120b',
    }
  }
  return analyses
}

export function generateTimeseriesPoint() {
  _tick++
  const profile = SCENARIO_PROFILES[_scenario]
  const latency = Math.max(10, Math.round(rand(profile.lat * 0.85, profile.lat * 1.15)))
  const errors  = Math.round(30 * profile.errRate * rand(0.7, 1.4))
  return {
    second:      new Date().toISOString().slice(0, 19),
    avg_latency: latency,
    req_count:   randInt(25, 35),
    errors,
  }
}

export function generateInitialTimeseries(points = 60) {
  const now = Date.now()
  return Array.from({ length: points }, (_, i) => {
    const t = new Date(now - (points - i) * 1000)
    const profile = SCENARIO_PROFILES['normal']
    const latency = Math.max(10, Math.round(rand(profile.lat * 0.8, profile.lat * 1.2)))
    return {
      second:      t.toISOString().slice(0, 19),
      avg_latency: latency,
      req_count:   randInt(26, 34),
      errors:      randInt(0, 1),
    }
  })
}

export function generateInitialHealthHistory(snapshots = 40) {
  const now = Date.now()
  return Array.from({ length: snapshots }, (_, i) => {
    const ts = now - (snapshots - i) * 5000
    const snap = {}
    for (const ep of ENDPOINTS) {
      snap[ep] = healthEntry('healthy', randInt(65, 95), 0)
    }
    return { ts, data: snap }
  })
}
