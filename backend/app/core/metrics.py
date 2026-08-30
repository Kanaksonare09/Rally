"""
Minimal, dependency-free in-process metrics registry. No prometheus_client
(or any new third-party dependency) — this is a small counter/gauge/
histogram-ish store good enough for a demo/hackathon deployment's `GET
/metrics`, not a claim to full Prometheus client-library semantics.

Deliberately never stores anything identifying a person or trip: metric
labels are a small, fixed vocabulary (HTTP method, status code, event
type...), never a user_id/trip_id/GPS coordinate/message body. See
app/api/metrics.py's module docstring for what /metrics does and doesn't
expose.

Process-local, like app/intelligence/worker.py's own health-status state —
resets on restart, which is fine for operational metrics; nothing here is
a source of truth for anything (that's always Postgres/Redis elsewhere).
Safe to call from any thread/coroutine: a single lock guards every
mutation, and increments are cheap enough that this is never a bottleneck
at this application's scale.
"""

import threading
from typing import Dict, Optional, Tuple

_lock = threading.Lock()

# name -> {label_tuple: value}. label_tuple is () for an unlabeled metric.
_counters: Dict[str, Dict[Tuple[Tuple[str, str], ...], float]] = {}
_gauges: Dict[str, Dict[Tuple[Tuple[str, str], ...], float]] = {}
# name -> {label_tuple: (count, sum)} — just enough to report an average;
# not real histogram buckets.
_observations: Dict[str, Dict[Tuple[Tuple[str, str], ...], Tuple[int, float]]] = {}


def _label_key(labels: Optional[Dict[str, str]]) -> Tuple[Tuple[str, str], ...]:
    if not labels:
        return ()
    return tuple(sorted(labels.items()))


def increment(name: str, labels: Optional[Dict[str, str]] = None, amount: float = 1.0) -> None:
    key = _label_key(labels)
    with _lock:
        bucket = _counters.setdefault(name, {})
        bucket[key] = bucket.get(key, 0.0) + amount


def set_gauge(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    key = _label_key(labels)
    with _lock:
        _gauges.setdefault(name, {})[key] = value


def observe(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    key = _label_key(labels)
    with _lock:
        bucket = _observations.setdefault(name, {})
        count, total = bucket.get(key, (0, 0.0))
        bucket[key] = (count + 1, total + value)


def snapshot() -> dict:
    """A plain-dict view of every metric, for tests and for GET /metrics'
    JSON mode."""
    with _lock:
        return {
            "counters": {name: dict(_fmt(vals)) for name, vals in _counters.items()},
            "gauges": {name: dict(_fmt(vals)) for name, vals in _gauges.items()},
            "observations": {
                name: {_label_str(k): {"count": c, "sum": s, "avg": (s / c if c else 0.0)} for k, (c, s) in vals.items()}
                for name, vals in _observations.items()
            },
        }


def _fmt(vals: Dict[Tuple[Tuple[str, str], ...], float]) -> Dict[str, float]:
    return {_label_str(k): v for k, v in vals.items()}


def _label_str(key: Tuple[Tuple[str, str], ...]) -> str:
    if not key:
        return "_"
    return ",".join(f'{k}="{v}"' for k, v in key)


def render_prometheus() -> str:
    """Plain Prometheus text-exposition format — no client library needed
    for a handful of counters/gauges this simple."""
    lines = []
    data = snapshot()
    for name, vals in data["counters"].items():
        lines.append(f"# TYPE rally_{name} counter")
        for label_str, value in vals.items():
            suffix = "" if label_str == "_" else "{" + label_str + "}"
            lines.append(f"rally_{name}{suffix} {value}")
    for name, vals in data["gauges"].items():
        lines.append(f"# TYPE rally_{name} gauge")
        for label_str, value in vals.items():
            suffix = "" if label_str == "_" else "{" + label_str + "}"
            lines.append(f"rally_{name}{suffix} {value}")
    for name, vals in data["observations"].items():
        lines.append(f"# TYPE rally_{name} summary")
        for label_str, agg in vals.items():
            suffix = "" if label_str == "_" else "{" + label_str + "}"
            lines.append(f"rally_{name}_count{suffix} {agg['count']}")
            lines.append(f"rally_{name}_sum{suffix} {agg['sum']}")
    return "\n".join(lines) + "\n"


def reset() -> None:
    """Test-only: clears every metric so tests don't see counts left over
    from other tests sharing this process-global registry."""
    with _lock:
        _counters.clear()
        _gauges.clear()
        _observations.clear()
