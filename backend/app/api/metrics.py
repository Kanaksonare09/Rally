"""
GET /metrics — operational metrics only (request counts/latency, error/
429 counts, WebSocket connection counts, Redis/DB failure counts,
intelligence/alert/SOS event counts — see app/core/metrics.py for the
full registry). Deliberately exposes NONE of: GPS coordinates, user ids,
trip/group ids, SOS messages, JWTs, or any other personal/private data —
every metric here is a plain count/gauge/average with, at most, a small
fixed-vocabulary label (HTTP method, status code, route template, event
type). This is not authenticated (matching the conventional Prometheus
scrape-endpoint pattern of trusting network-level access control, e.g. a
private scrape network) — if that's ever a concern for a given
deployment, put it behind the reverse proxy the way /health commonly is.
"""

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from app.core import metrics
from app.websocket.manager import manager

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def get_metrics(format: str = Query("prometheus", pattern="^(prometheus|json)$")):
    # Refreshed on read rather than only on connect/disconnect, so a
    # scrape always reflects the current count even between events.
    metrics.set_gauge("websocket_active_connections", manager.total_connection_count())

    if format == "json":
        return metrics.snapshot()
    return PlainTextResponse(metrics.render_prometheus(), media_type="text/plain; version=0.0.4")
