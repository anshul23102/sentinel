FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user — the app never needs root, and staying root
# means a compromise of the process (or of any dependency in it) starts
# with root inside the container instead of a properly scoped account.
RUN useradd --create-home --uid 1000 sentinel && chown -R sentinel:sentinel /app
USER sentinel

EXPOSE 8000

# --forwarded-allow-ips="" disables uvicorn's own independent trust of
# X-Forwarded-For from loopback connections (its default) — the app-level
# TRUST_PROXY_HEADERS setting in ratelimit.py is the single toggle for
# whether this deployment is behind a real reverse proxy; see its comment.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--forwarded-allow-ips="]
