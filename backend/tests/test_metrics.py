"""
app/core/metrics.py: the in-process registry itself, plus GET /metrics'
two output formats. reset() runs before each test so counts from other
test modules (which also hit real endpoints and increment real metrics)
never leak into these assertions.
"""

import pytest
from fastapi.testclient import TestClient

from app.core import metrics
from app.core.config import settings
from app.main import app

client = TestClient(app)
API = settings.API_V1_STR


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset()
    yield
    metrics.reset()


def test_increment_default_is_one():
    metrics.increment("widgets_total")
    assert metrics.snapshot()["counters"]["widgets_total"]["_"] == 1.0


def test_increment_accumulates():
    metrics.increment("widgets_total")
    metrics.increment("widgets_total")
    metrics.increment("widgets_total", amount=3)
    assert metrics.snapshot()["counters"]["widgets_total"]["_"] == 5.0


def test_increment_with_labels_are_independent_buckets():
    metrics.increment("requests_total", {"method": "GET"})
    metrics.increment("requests_total", {"method": "POST"})
    metrics.increment("requests_total", {"method": "GET"})
    counters = metrics.snapshot()["counters"]["requests_total"]
    assert counters['method="GET"'] == 2.0
    assert counters['method="POST"'] == 1.0


def test_set_gauge_overwrites_not_accumulates():
    metrics.set_gauge("active_connections", 3)
    metrics.set_gauge("active_connections", 7)
    assert metrics.snapshot()["gauges"]["active_connections"]["_"] == 7.0


def test_observe_tracks_count_sum_and_average():
    metrics.observe("latency_ms", 10.0)
    metrics.observe("latency_ms", 20.0)
    metrics.observe("latency_ms", 30.0)
    agg = metrics.snapshot()["observations"]["latency_ms"]["_"]
    assert agg["count"] == 3
    assert agg["sum"] == 60.0
    assert agg["avg"] == 20.0


def test_reset_clears_everything():
    metrics.increment("x")
    metrics.set_gauge("y", 1)
    metrics.observe("z", 1.0)
    metrics.reset()
    snap = metrics.snapshot()
    assert snap["counters"] == {}
    assert snap["gauges"] == {}
    assert snap["observations"] == {}


def test_render_prometheus_includes_type_and_value_lines():
    metrics.increment("widgets_total", {"kind": "a"})
    text = metrics.render_prometheus()
    assert "# TYPE rally_widgets_total counter" in text
    assert 'rally_widgets_total{kind="a"} 1.0' in text


# ---- GET /metrics -----------------------------------------------------


def test_metrics_endpoint_prometheus_format_by_default():
    metrics.increment("demo_total")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "rally_demo_total" in response.text


def test_metrics_endpoint_json_format():
    metrics.increment("demo_total")
    response = client.get("/metrics?format=json")
    assert response.status_code == 200
    body = response.json()
    assert "counters" in body
    assert "demo_total" in body["counters"]


def test_metrics_endpoint_rejects_unknown_format():
    response = client.get("/metrics?format=xml")
    assert response.status_code == 422


def test_metrics_never_exposes_secrets_or_gps():
    metrics.increment("demo_total")
    text = client.get("/metrics").text
    for forbidden in ("SUPABASE_SERVICE_ROLE_KEY", "JWT_SECRET", "latitude", "longitude", "Bearer "):
        assert forbidden not in text


def test_metrics_endpoint_reports_websocket_gauge():
    response = client.get("/metrics?format=json")
    assert "websocket_active_connections" in response.json()["gauges"]
