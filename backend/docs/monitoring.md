# Backend monitoring

## Health — `GET /health`

JSON overview of service readiness. Always returns HTTP **200**; overall health is in the body.

| Field | Meaning |
|-------|---------|
| `status` | `ok` if critical checks pass, otherwise `degraded` |
| `service` | `applied-ai-marketing-agent` |
| `version` | from settings (`app_version`) |
| `components.storage` | data dir / posts file writable (`up` / `down`) |
| `components.memory` | short HTTP probe of `MCP_MEMORY_URL` (`up` / `down`) |
| `components.huggingface` | `configured: true` if `HF_TOKEN` is set (no live HF call) |
| `components.web_search` | `enabled` from `WEB_SEARCH_ENABLED` |

Example (Docker Compose backend port **8080**):

```bash
curl http://localhost:8080/health
```

## Metrics — `GET /metrics`

Prometheus text exposition (scrape target). Includes:

- **HTTP defaults** from `prometheus-fastapi-instrumentator` (`http_requests_total`, request duration histograms, …)
- **Process / Python** gauges from `prometheus-client`
- **Manager graph custom counters** (see below)

```bash
curl http://localhost:8080/metrics
```

Local uvicorn often uses port `8000` instead of `8080`.

### Custom Manager counters

| Metric | Labels | When |
|--------|--------|------|
| `manager_chat_requests_total` | `status` | After each graph run (`success`, `needs_input`, `error`, …) or `exception` on hard failure |
| `manager_chat_intent_total` | `intent` | After intent classification |
| `manager_chat_route_total` | `target` | Intent-router destination node |
| `manager_specialist_total` | `agent`, `status` | Text/image specialist outcome |
| `manager_validation_total` | `result` | Artifact validation decision |

No separate Prometheus server is required; point a scraper at the backend `/metrics` URL.
