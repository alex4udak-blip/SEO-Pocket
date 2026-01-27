# Railway Setup for SEO-Pocket

## Add FlareSolverr Service

1. Go to your Railway project dashboard
2. Click "New Service" → "Docker Image"
3. Enter image: `ghcr.io/flaresolverr/flaresolverr:latest`
4. Add environment variable: `LOG_LEVEL=info`
5. Deploy

## Configure Backend

Add this environment variable to your backend service:
```
FLARESOLVERR_URL=http://flaresolverr.railway.internal:8191/v1
```

Note: Railway uses internal networking with `.railway.internal` domain.

## Optional: Czech Proxy

If you have a Czech proxy for additional fallback:
```
PROXY_URL=http://user:pass@host:port
```

## Services Overview

| Service | Port | Purpose |
|---------|------|---------|
| backend | 8000 | Main API |
| flaresolverr | 8191 | Cloudflare bypass |
