# Grip Platform: Deployment Guide

---

## 1. Environment Variables

Create a `.env` file in the project root:

```ini
PORT=8000
HOST=0.0.0.0

# Browser automation settings
BROWSER_HEADLESS=true
BROWSER_USER_DATA_DIR=data/profile

# Provider selection
GRIP_DEFAULT_PROVIDER=google

# Rate Limiting & Cache
RATE_LIMIT_CAPACITY=60
RATE_LIMIT_REFILL_PER_SEC=2.0
CACHE_TTL=3600
```

---

## 2. Docker Compose Deployment

To build and start the complete platform including API service and background worker:

```bash
cd deploy
docker compose up -d --build
```

Verify service logs:
```bash
docker compose logs -f api
```

---

## 3. Production Nginx Reverse Proxy

A production `nginx.conf` template is included in `deploy/production/nginx.conf` with Server-Sent Events (SSE) buffering disabled for real-time responsiveness.
