"""
Every Redis key and channel name RALLY uses, in one place, so nothing
outside this module ever hand-builds a key string. All live-trip state
lives under the `trip:{trip_id}:...` namespace; see the backend README's
Redis section for what belongs here versus in Supabase.
"""

def live_location_key(trip_id, user_id) -> str:
    """Current location for one user on one trip. TTL'd — see
    live_state_service.set_live_location()."""
    return f"trip:{trip_id}:user:{user_id}:location"


def trip_users_key(trip_id) -> str:
    """Redis Set of user ids with a live location on this trip. Members
    are added on the first location update and removed on trip cleanup —
    this set is a convenience index, never the source of truth for group
    membership (Supabase/group_members is authoritative for that)."""
    return f"trip:{trip_id}:users"


def presence_key(trip_id, user_id) -> str:
    """TTL'd marker: while this key exists, the user counts as ONLINE for
    the trip. Refreshed on every heartbeat/location_update; once it
    expires, the user is STALE/OFFLINE."""
    return f"trip:{trip_id}:presence:{user_id}"


def trip_channel(trip_id) -> str:
    """Redis Pub/Sub channel every FastAPI instance with local WebSocket
    connections for this trip subscribes to — the cross-instance broadcast
    mechanism (see app/websocket/manager.py)."""
    return f"trip:{trip_id}:events"


# --- Intelligence engine (app/intelligence/) -------------------------------
#
# Everything below is short-lived calculation state — debounce timers,
# dedup guards, a per-trip evaluation lock. None of it is ever the record
# of a detection; that's the intelligence_events table in Postgres.


def intel_movement_state_key(trip_id, user_id) -> str:
    """The debounce state behind hysteresis in app/intelligence/movement.py
    — {"state": "MOVING", "since": "<iso>"}. No TTL: it's overwritten on
    every evaluation and is harmless if it lingers past a trip's end."""
    return f"trip:{trip_id}:intel:user:{user_id}:movement"


def intel_condition_key(trip_id, event_type, user_id="group") -> str:
    """Persistence-tracking state behind each detector's "how long has this
    condition held" requirement — {"since": "<iso>"}. `user_id` defaults to
    the literal string "group" for group-level conditions (GROUP_SEPARATION,
    MOVING_TOGETHER) that aren't about one specific member."""
    return f"trip:{trip_id}:intel:condition:{event_type}:{user_id}"


def intel_active_event_key(trip_id, event_type, user_id="group") -> str:
    """Fast-path "is there already an active DB event for this
    (trip, event_type, subject)" check, holding that event's id. The real
    dedup guarantee is the partial unique index on intelligence_events
    (see app/models/intelligence_event.py) — this key just avoids hitting
    the database to find out on every evaluation tick."""
    return f"trip:{trip_id}:intel:event:{event_type}:{user_id}"


def intel_eval_lock_key(trip_id) -> str:
    """SET NX PX lock so at most one worker evaluates a given trip at a
    time — see app/intelligence/engine.py."""
    return f"trip:{trip_id}:intel:lock"


# --- Alerts (app/alerts/) --------------------------------------------------


def alert_dedup_lock_key(event_id) -> str:
    """Short-lived SET NX PX lock guarding "create the alert for this
    intelligence event" against two concurrent evaluations — belt-and-
    suspenders alongside the database's own partial unique index on
    alerts(event_id) WHERE resolved_at IS NULL (see app/models/alert.py)."""
    return f"alert:dedup:{event_id}"


# --- SOS (app/sos/) ---------------------------------------------------------
#
# A convenience mirror of "this SOS is currently active," never the only
# copy — PostgreSQL's sos_events table is the permanent record regardless
# of what happens to this key. No TTL: SOS lifecycle is governed
# exclusively by explicit acknowledge/resolve/cancel, never by expiry
# (see the SOS SAFETY RULE in app/sos/service.py's module docstring).


def sos_active_key(trip_id, sos_id) -> str:
    return f"trip:{trip_id}:sos:{sos_id}"


def trip_active_sos_key(trip_id) -> str:
    """Redis Set of currently-active SOS ids for the trip — a convenience
    index only; GET endpoints still read from Postgres, never from this
    set alone (see the module docstring in app/sos/service.py)."""
    return f"trip:{trip_id}:sos:active"


# --- Route intelligence (app/route/) ----------------------------------------
#
# Same rule as the intelligence-engine keys above: cheap read-through cache
# only. Postgres/location_history stay authoritative; nothing here is ever
# the sole copy of a value a client can query.


def route_progress_key(trip_id, user_id) -> str:
    """Last-computed RouteMatch/progress snapshot for one user on one trip
    — read by GET /trips/{trip_id}/route/progress as a cache-first layer,
    recomputed (and this key refreshed) on every intelligence evaluation
    tick that has a live location to match. TTL'd the same as a live
    location, since a progress snapshot with no fresh location behind it
    is stale by definition. Postgres (location_history + the routes table)
    remains authoritative — this is a read-through cache only."""
    return f"trip:{trip_id}:route:user:{user_id}:progress"


def trip_analytics_cache_key(trip_id) -> str:
    """Read-through cache for a COMPLETED trip's computed analytics
    (app/analytics/trip_analytics.py) — TTL'd (ANALYTICS_CACHE_TTL_SECONDS),
    never the source of truth. Postgres (and, once generated, the
    trip_analytics_snapshots table) remains authoritative; losing this key
    just means the next request recomputes instead of hitting cache. Never
    used for an ACTIVE trip — that's live data, not something to cache
    behind a multi-minute TTL."""
    return f"trip:{trip_id}:analytics"


def weather_cache_key(lat_bucket: float, lon_bucket: float) -> str:
    """Cached provider response for one coordinate, rounded to ~1km
    resolution before being used as a key (see app/weather/service.py) —
    two members/trips within the same rough area share a cache entry
    instead of each paying for their own API call. TTL'd
    (WEATHER_CACHE_TTL_SECONDS); losing this key just means the next
    request re-fetches, never a correctness issue."""
    return f"weather:{lat_bucket}:{lon_bucket}"


def route_condition_key(trip_id, condition: str, user_id) -> str:
    """Persistence-tracking state behind route-progress debounce
    requirements that aren't a full IntelligenceEventType (e.g. confirming
    ARRIVED only after ARRIVAL_DURATION_SECONDS of sustained proximity) —
    same {"since": "<iso>"} shape and reset-on-false behavior as
    app.intelligence.detectors._condition_elapsed_seconds, kept as its own
    helper in app/route/progress.py since it isn't gating a persisted
    intelligence_events row."""
    return f"trip:{trip_id}:route:condition:{condition}:{user_id}"
