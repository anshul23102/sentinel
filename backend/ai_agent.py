from groq import Groq
import json
import os
from datetime import datetime
from db import get_endpoint_stats, get_recent_anomalies
from anomaly_detector import get_health_snapshot

_api_key = os.environ.get("GROQ_API_KEY", "")
client = Groq(api_key=_api_key) if _api_key else None
MODEL = "llama-3.3-70b-versatile"

def _get_client():
    global client, _api_key
    if client is None:
        _api_key = os.environ.get("GROQ_API_KEY", "")
        if _api_key:
            client = Groq(api_key=_api_key)
    return client

BASE_SYSTEM_PROMPT = """You are Sentinel, an expert SRE AI embedded inside a live API monitoring dashboard.
You have real-time access to API health, error rates, latency metrics, and anomaly logs for NexusCommerce.

Personality:
- Direct, concise, sharp — engineers need fast answers at 3AM
- Match the tone to the question: diagnostic questions get structured analysis, follow-up questions get conversational replies
- Do NOT always repeat "Root Cause / Evidence / Fix Steps" — only use that structure when you are doing a fresh diagnosis
- If someone asks a follow-up like "are you sure?", "why?", "tell me more", "how do I fix it?", respond conversationally based on what was already discussed
- Use technical terminology but be clear
- Format root cause chains as: ServiceA → ServiceB → Impact
- Use bullet points and bold headers only when it aids clarity, not as a template

When diagnosing a fresh issue, look for:
1. Error cascades (one service failing causing others to fail)
2. Latency correlation (slow DB → slow API → user timeouts)
3. Traffic patterns (sudden spikes, drops, rate limiting)
4. Service dependencies (root vs downstream victim)"""

def _build_system_with_context(health: dict, recent_anomalies: list, stats: list) -> str:
    """Inject live system state into the system message so user messages stay clean."""
    KEYS = {'anomaly_type', 'severity', 'endpoint', 'description', 'detected_at'}
    trimmed = [{k: v for k, v in a.items() if k in KEYS} for a in recent_anomalies[:5]]
    context_block = (
        "\n\n--- LIVE SYSTEM STATE (refreshed now) ---\n"
        "Health snapshot:\n" + json.dumps(health, indent=2) + "\n\n"
        f"Recent anomalies ({len(recent_anomalies)} detected):\n"
        + json.dumps(trimmed, indent=2) + "\n\n"
        "Endpoint stats (last 5 min):\n" + json.dumps(stats, indent=2)
        + "\n--- END LIVE STATE ---"
    )
    return BASE_SYSTEM_PROMPT + context_block

def _generate(prompt: str, max_tokens: int = 600) -> str:
    c = _get_client()
    if not c:
        return "AI unavailable: GROQ_API_KEY not configured."
    response = c.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": BASE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        max_tokens=max_tokens,
        temperature=0.5,
    )
    return response.choices[0].message.content

async def analyze_anomaly(anomaly: dict, recent_logs: list[dict]) -> dict:
    log_summary = _summarize_logs(recent_logs, anomaly["endpoint"])
    health = get_health_snapshot()

    prompt = f"""ANOMALY: {anomaly['anomaly_type']} on {anomaly['endpoint']} — Severity: {anomaly['severity']}
Description: {anomaly['description']}
Detected at: {anomaly['detected_at']}

Heuristic chain: {json.dumps(anomaly.get('root_cause_chain', []))}

System health at detection:
{json.dumps(health, indent=2)}

Log data for {anomaly['endpoint']} (last 60s):
{json.dumps(log_summary, indent=2)}

Give a sharp SRE diagnosis: what is actually happening, why, and the top 3 immediate actions to resolve it.
Be specific to this anomaly — reference actual numbers from the logs. Under 250 words."""

    analysis = _generate(prompt)
    return {
        "anomaly_id": anomaly.get("id"),
        "analysis": analysis,
        "analyzed_at": datetime.utcnow().isoformat(),
        "model": MODEL,
    }

async def chat_stream(message: str, conversation_history: list[dict]):
    """Streaming version — yields text chunks as they arrive from Groq."""
    health          = get_health_snapshot()
    recent_anomalies = await get_recent_anomalies(10)
    stats           = await get_endpoint_stats(5)

    system_with_context = _build_system_with_context(health, recent_anomalies, stats)

    messages = [{"role": "system", "content": system_with_context}]
    for msg in conversation_history[-8:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    c = _get_client()
    if not c:
        yield "AI unavailable: GROQ_API_KEY not configured."
        return
    stream = c.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=600,
        temperature=0.55,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta

async def chat(message: str, conversation_history: list[dict]) -> str:
    health = get_health_snapshot()
    recent_anomalies = await get_recent_anomalies(10)
    stats = await get_endpoint_stats(5)

    # Live context goes into the system prompt ONCE — keeps conversation history clean
    # so the model can actually follow the thread instead of re-anchoring on the same data
    system_with_context = _build_system_with_context(health, recent_anomalies, stats)

    messages = [{"role": "system", "content": system_with_context}]

    # Replay conversation history with clean messages (no embedded context blobs)
    for msg in conversation_history[-8:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Current user message — just the raw text, no context injected here
    messages.append({"role": "user", "content": message})

    c = _get_client()
    if not c:
        return "AI unavailable: GROQ_API_KEY not configured."
    response = c.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=600,
        temperature=0.55,
    )
    return response.choices[0].message.content

async def generate_incident_report(anomalies: list[dict], duration_minutes: int) -> str:
    prompt = f"""Generate a concise incident report for the following anomalies detected over {duration_minutes} minutes:

{json.dumps(anomalies, indent=2)}

Format:
## Incident Summary
[1-2 sentences]

## Timeline
[Key events with timestamps]

## Root Cause
[Most likely cause with evidence]

## Impact
[Services affected, estimated user impact]

## Resolution Steps
[Numbered steps taken or recommended]

## Prevention
[2-3 specific actions to prevent recurrence]

Keep it engineering-focused, under 400 words."""

    return _generate(prompt, max_tokens=800)

def _summarize_logs(logs: list[dict], endpoint: str) -> dict:
    endpoint_logs = [l for l in logs if l["endpoint"] == endpoint]
    if not endpoint_logs:
        return {"message": "No logs found for this endpoint"}

    total = len(endpoint_logs)
    errors = [l for l in endpoint_logs if l["status_code"] >= 500]
    latencies = [l["latency_ms"] for l in endpoint_logs]
    error_msgs = list({l["error_message"] for l in errors if l.get("error_message")})[:5]

    return {
        "total_requests": total,
        "error_count": len(errors),
        "error_rate": round(len(errors) / total, 3) if total else 0,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
        "max_latency_ms": max(latencies) if latencies else 0,
        "unique_error_messages": error_msgs,
        "status_distribution": _count_by(endpoint_logs, "status_code"),
    }

def _count_by(items: list[dict], key: str) -> dict:
    counts: dict = {}
    for item in items:
        val = str(item.get(key, "unknown"))
        counts[val] = counts.get(val, 0) + 1
    return dict(sorted(counts.items()))
