// Generates realistic mock data when the backend is unavailable (Railway sleeping, etc.)

const ENDPOINTS = [
  '/api/auth', '/api/checkout', '/api/cart', '/api/products',
  '/api/search', '/api/inventory', '/api/payments', '/api/notifications',
]

const SERVICES = {
  '/api/auth':          { name: 'Auth',          deps: [] },
  '/api/checkout':      { name: 'Checkout',       deps: ['/api/auth', '/api/cart', '/api/payments'] },
  '/api/cart':          { name: 'Cart',           deps: ['/api/auth', '/api/inventory'] },
  '/api/products':      { name: 'Products',       deps: ['/api/inventory'] },
  '/api/search':        { name: 'Search',         deps: ['/api/products'] },
  '/api/inventory':     { name: 'Inventory',      deps: [] },
  '/api/payments':      { name: 'Payments',       deps: [] },
  '/api/notifications': { name: 'Notifications',  deps: ['/api/auth'] },
}

function rand(min, max) { return min + Math.random() * (max - min) }
function randInt(min, max) { return Math.floor(rand(min, max + 1)) }
function pick(arr) { return arr[randInt(0, arr.length - 1)] }

// Scenario profiles: [baseLatency, latencyJitter, errorRate]
const SCENARIO_PROFILES = {
  normal:        { lat: 80,  jitter: 25,  errRate: 0.005 },
  db_slowdown:   { lat: 480, jitter: 180, errRate: 0.18  },
  memory_leak:   { lat: 160, jitter: 80,  errRate: 0.06  },
  rate_limit:    { lat: 95,  jitter: 30,  errRate: 0.22  },
  net_partition: { lat: 210, jitter: 90,  errRate: 0.35  },
}

let _scenario = 'normal'
let _tick = 0

export function setMockScenario(s) { _scenario = SCENARIO_PROFILES[s] ? s : 'normal' }
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
      ? (_scenario === 'rate_limit' ? 429 : _scenario === 'net_partition' ? 503 : pick([500, 502, 503]))
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
    rate_limit:    ['rate limit exceeded: 429', 'too many requests', 'quota exhausted'],
    net_partition: ['ECONNREFUSED', 'network unreachable', 'timeout: upstream unavailable'],
  }
  return pick(msgs[scenario] || ['internal server error'])
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
    snap[ep] = {
      endpoint: ep,
      status,
      avg_latency: latency,
      error_rate:  errPct,
      request_count: randInt(180, 300),
      p95_latency: Math.round(latency * 1.6),
    }
  }
  return snap
}

export function generateAnomalies() {
  if (_scenario === 'normal') return []
  const now = new Date()
  const chains = {
    db_slowdown:   [
      { service: '/api/auth',     impact: 'Auth latency +340%' },
      { service: '/api/cart',     impact: 'Cart timeouts increasing' },
      { service: '/api/checkout', impact: 'Checkout cascade failure' },
    ],
    memory_leak:   [
      { service: '/api/search',   impact: 'Search heap at 87%' },
      { service: '/api/products', impact: 'Products response degraded' },
    ],
    rate_limit:    [
      { service: '/api/auth',     impact: 'Auth returning 429' },
      { service: '/api/checkout', impact: 'Checkout blocked — no auth tokens' },
      { service: '/api/payments', impact: 'Payment flow halted' },
    ],
    net_partition: [
      { service: '/api/inventory',  impact: 'Inventory unreachable' },
      { service: '/api/cart',       impact: '65% of cart reads failing' },
      { service: '/api/checkout',   impact: 'Checkout ECONNREFUSED' },
    ],
  }
  const chain = chains[_scenario] || []
  return chain.map((c, i) => ({
    id: 1000 + i,
    anomaly_type: _scenario === 'db_slowdown' ? 'latency_spike'
                : _scenario === 'memory_leak'  ? 'memory_pressure'
                : _scenario === 'rate_limit'   ? 'error_surge'
                : 'connectivity_failure',
    severity: i === 0 ? 'critical' : 'high',
    endpoint: c.service,
    description: c.impact,
    detected_at: new Date(now - (chain.length - i) * 12000).toISOString(),
    root_cause_chain: chain.slice(0, i + 1).map(x => x.service),
    value: rand(200, 900),
    threshold: 200,
    z_score: rand(3.2, 8.5),
  }))
}

export function generateAiAnalyses(anomalies) {
  const analyses = {}
  const texts = {
    db_slowdown:   'Connection pool exhausted on /api/auth (pool size: 10, demand: 28). Auth latency exceeded 500ms SLA, cascading timeouts to cart and checkout. Immediate actions: (1) increase pool size to 50 in DATABASE_POOL_SIZE env var, (2) add circuit breaker on cart → auth calls, (3) restart auth pod to clear stale connections.',
    memory_leak:   'Heap growing at ~12MB/min on search service. GC pause times now 200ms+, causing P95 latency to hit 620ms. Likely culprit: unbounded in-memory cache in product indexer. Actions: (1) cap cache size with LRU eviction, (2) restart search service now to recover heap, (3) add memory alert at 70% threshold.',
    rate_limit:    'Auth service rate limit hit — 429s flooding all downstream. Root cause: bot traffic spike from crawler subnet 54.23.x.x (1,200 rps). Actions: (1) block subnet in WAF, (2) raise auth rate limit to 2,000 rpm for internal services, (3) add Retry-After header to 429 responses.',
    net_partition: 'Network partition isolating inventory service — ECONNREFUSED from us-east-1b AZ. 65% of cart reads failing. Actions: (1) reroute inventory traffic to us-east-1a replica, (2) enable stale-read fallback for cart service, (3) file incident with infra team for AZ recovery.',
  }
  for (const a of anomalies) {
    analyses[a.id] = {
      anomaly_id:  a.id,
      analysis:    texts[_scenario] || 'Anomaly detected. Investigate recent deployments and traffic patterns.',
      analyzed_at: a.detected_at,
      model:       'llama-3.3-70b-versatile',
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
      snap[ep] = { endpoint: ep, status: 'healthy', avg_latency: randInt(65, 95), error_rate: 0 }
    }
    return { ts, data: snap }
  })
}
