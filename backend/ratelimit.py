import hmac
import os
import time
from fastapi import Request, HTTPException

import state

ADMIN_API_KEY   = os.environ.get("ADMIN_API_KEY", "")
# Off by default so the public demo stays interactive for anonymous visitors
# (rate limiting above is the always-on protection for that case). Set this
# to require ADMIN_API_KEY on every guarded route instead — for a private or
# staging deployment where you want a hard lockdown, not just throttling.
REQUIRE_API_KEY = os.environ.get("REQUIRE_API_KEY", "").lower() in ("1", "true", "yes")

# Off by default — X-Forwarded-For is a plain client-supplied header unless
# something in front of this process actually sets it and strips any
# value the caller tried to send. Trusting it unconditionally lets any
# caller put an arbitrary value there and get a fresh rate-limit bucket on
# every request, i.e. bypass the limiter entirely. Only enable this when
# deployed behind a reverse proxy (Render/Vercel/nginx/etc.) that you've
# confirmed overwrites X-Forwarded-For rather than appending to it.
TRUST_PROXY_HEADERS = os.environ.get("TRUST_PROXY_HEADERS", "").lower() in ("1", "true", "yes")

def _api_key_matches(request: Request) -> bool:
    """Constant-time comparison — a plain == leaks timing information about
    how many leading characters matched, which is a textbook side channel
    for recovering a secret one byte at a time."""
    if not ADMIN_API_KEY:
        return False
    supplied = request.headers.get("x-api-key", "")
    return hmac.compare_digest(supplied, ADMIN_API_KEY)

def _client_ip(request: Request) -> str:
    if TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def rate_limit(bucket: str, limit: int, window_seconds: int):
    """FastAPI dependency factory — fixed-window counter in Redis (atomic INCR,
    TTL via EXPIRE). Standard textbook rate-limiting pattern: O(1) per request,
    no extra memory beyond one counter per (client, window). A sliding-window
    log would be more precise at window boundaries but isn't worth the added
    complexity for a per-IP demo-abuse guard.

    A request carrying the correct X-API-Key bypasses the limit entirely —
    that's the owner's key, so a live demo/interview session is never
    self-throttled while anonymous visitors still get the guard.
    """
    async def _dependency(request: Request):
        if _api_key_matches(request):
            return
        ip = _client_ip(request)
        window = int(time.time() // window_seconds)
        key = f"sentinel:ratelimit:{bucket}:{ip}:{window}"

        c = state.get_client()
        count = await c.incr(key)
        if count == 1:
            await c.expire(key, window_seconds)

        if count > limit:
            ttl = await c.ttl(key)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded for {bucket}: {limit} requests per {window_seconds}s. Try again in {max(ttl, 1)}s.",
                headers={"Retry-After": str(max(ttl, 1))},
            )
    return _dependency


async def require_api_key(request: Request) -> None:
    """Optional hard gate for the same guarded routes — a no-op unless
    REQUIRE_API_KEY is enabled, so the default stays the public-demo
    experience. When enabled, every caller (not just ones over the rate
    limit) must carry the matching X-API-Key header."""
    if not REQUIRE_API_KEY:
        return
    if not _api_key_matches(request):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
