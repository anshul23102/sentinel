# Security Policy

## Reporting a Vulnerability

If you find a security issue in Sentinel, please do not open a public GitHub issue for it. Instead, report it privately through [GitHub's Security Advisories](https://github.com/anshul23102/sentinel/security/advisories/new) for this repository, or email the maintainer directly at anshul23102@iiitd.ac.in.

Include what you found, the steps to reproduce it, and what you think the impact is. You should get a response within a few days. Once a fix is ready, you will be credited in the advisory unless you ask not to be.

## Supported Versions

Sentinel is a single, actively developed project on `main`. Security fixes land on `main` only, there are no maintained release branches to backport to.

## Threat Model

Sentinel is a public, multi-tenant demo application. Anyone can open it and get their own isolated simulated world, identified by a session id. That design choice shapes what is and is not treated as a vulnerability here:

**In scope:**
- Anything that lets one session read, modify, or interfere with another session's data
- Anything that lets an unauthenticated caller degrade the service for other users (resource exhaustion, unbounded session creation, rate limit bypass)
- SQL injection, command injection, or any other injection into the database, Redis, or the LLM call
- Secrets (API keys, credentials) leaking through logs, error responses, or the frontend bundle
- Cross-site scripting through anomaly data, chat responses, or any other user-reachable rendering path
- Authentication or authorization bypass on the routes that are meant to be gated (`REQUIRE_API_KEY`, rate limiting)

**Explicitly out of scope, by design:**
- A caller with no `X-Session-Id` header getting a fresh anonymous session. That is the intended behavior for a public demo, not a bypass.
- A caller reading or manipulating their own session's data. It is their session.
- Denial of service against your own deployment by exhausting your own configured limits (`MAX_SESSIONS`, rate limit thresholds). Those are operator-configurable, not fixed guarantees.

## Deployment Notes for Operators

The defaults here are tuned for a public interactive demo, not a locked-down internal tool. If you are deploying Sentinel somewhere that matters, read `backend/.env.example` and set these deliberately:

- **`REQUIRE_API_KEY`** is off by default so anonymous visitors can use the live demo. Turn it on for a private or staging deployment.
- **`TRUST_PROXY_HEADERS`** is off by default. Only turn it on if you are behind a reverse proxy that you have confirmed overwrites `X-Forwarded-For` rather than passing through whatever the client sent. If you enable it without a proxy in front, or behind a proxy that does not sanitize the header, every rate limit in the app becomes trivially bypassable. If you run the backend directly with uvicorn (not through the provided Dockerfile), also pass `--forwarded-allow-ips=""` explicitly, uvicorn has its own independent trust of `X-Forwarded-For` from loopback connections that is separate from this app-level setting.
- **`MAX_SESSIONS`** bounds how many concurrent simulated worlds this process will run at once. Size it to what your Postgres pool and Redis instance can actually hold.
- **`CORS_ORIGINS`** must list your real deployed frontend origin. Do not set it to `*`.
- Never commit `backend/.env`. It is already gitignored, keep it that way.

## Known Limitations

These are accepted tradeoffs for a demo-first project, not oversights, but worth stating plainly rather than leaving implicit:

- Session identity is a client-supplied, unauthenticated string. It is validated for shape and rate-limited on creation, but it is not a real authentication mechanism. Do not put anything in a session that would matter if another party learned the session id.
- Prompt-injection defenses on the AI chat endpoint (`prompt_guard.py`) are heuristic, layered defense-in-depth, not a guarantee. No pattern list catches every phrasing, and no system-prompt instruction is unconditionally obeyed by an LLM.
