import os
import time
from fastapi import Request, HTTPException

import state

ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")

def _client_ip(request: Request) -> str:
    # Respect a trusted reverse proxy's forwarded header if present (Render/Vercel
    # style deploys); falls back to the direct connection for local dev.
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
        if ADMIN_API_KEY and request.headers.get("x-api-key") == ADMIN_API_KEY:
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
