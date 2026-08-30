# RALLY Backend

FastAPI backend for RALLY. Supabase Postgres + PostGIS is the only database;
Supabase Auth is the only identity provider. FastAPI never stores passwords
and never issues its own tokens — it only verifies tokens Supabase already
issued.

## Authentication

```
Next.js  --(email/password or OAuth)-->  Supabase Auth
Next.js  <--(access token)--  Supabase Auth
Next.js  --(Authorization: Bearer <token>)-->  FastAPI
FastAPI  --(verify signature, expiry, audience, issuer)-->  Authenticated user
```

1. The frontend signs the user in via `supabase-js` (`supabase.auth.signInWithPassword`,
   OAuth, etc.). FastAPI is never involved in this step.
2. Supabase returns a JWT access token to the frontend
   (`data.session.access_token`).
3. The frontend sends it on every request to FastAPI:

   ```
   Authorization: Bearer <SUPABASE_ACCESS_TOKEN>
   ```

4. FastAPI verifies the token in `app/core/security.py` — checks the
   signature against `JWT_SECRET`, expiry, the `authenticated` audience, and
   (when `SUPABASE_URL` is set) the issuer. It never trusts a user id
   supplied any other way.
5. `get_current_user()` (in `app/dependencies/auth.py`) returns the
   verified `{id, email}`. `get_current_profile()` builds on top of it to
   fetch (or create, on first login) the matching row in `profiles`.

### `GET /api/v1/auth/me`

Requires `Authorization: Bearer <token>`.

| Case | Response |
|---|---|
| No header | `401` |
| Malformed header / wrong scheme | `401` |
| Invalid or unsigned-by-us token | `401` |
| Expired token | `401` |
| Valid token | `200` |

```json
{
  "id": "b2b1...",
  "email": "user@example.com",
  "profile": { "full_name": "Ada Lovelace", "avatar_url": null }
}
```

If this is the user's first authenticated request, a `profiles` row is
created automatically, seeded from `user_metadata.full_name` /
`user_metadata.avatar_url` when Supabase provided them (never guaranteed —
falls back to `null`).

## Trips

A trip belongs to a group and moves through a small state machine:

```
CREATED -> ACTIVE -> COMPLETED
CREATED -> CANCELLED
```

`COMPLETED` and `CANCELLED` are terminal — every other transition (starting
a trip twice, cancelling an active trip, etc.) is rejected with `409
INVALID_TRIP_STATE`. A group can have at most one `ACTIVE` trip at a time;
this is enforced both as an app-level pre-check (a friendly `409
ACTIVE_TRIP_EXISTS` on the common path) and, more importantly, as a
**partial unique index** in Postgres (`uq_trips_one_active_per_group`,
`UNIQUE(group_id) WHERE status = 'ACTIVE'`, added in migration `0002`) —
that's what actually stops two concurrent "start trip" requests from both
succeeding.

| Endpoint | Who | Effect |
|---|---|---|
| `POST /api/v1/groups/{group_id}/trips` | active group member | creates a trip in `CREATED` |
| `GET /api/v1/groups/{group_id}/trips` | active group member | lists the group's trips, newest first |
| `GET /api/v1/trips/{trip_id}` | active member of the trip's group | trip detail |
| `POST /api/v1/trips/{trip_id}/start` | active member of the trip's group | `CREATED -> ACTIVE` |
| `POST /api/v1/trips/{trip_id}/end` | active member of the trip's group | `ACTIVE -> COMPLETED` |
| `POST /api/v1/trips/{trip_id}/cancel` | the trip's creator, or the group leader | `CREATED -> CANCELLED` |

`started_by` always comes from the verified JWT — never from the request
body. A trip that doesn't exist and a trip whose group the caller isn't an
active member of both return the same `404 TRIP_NOT_FOUND`, so a client
can't distinguish "wrong id" from "not your trip."

Trips are never deleted by these endpoints — completed and cancelled trips
stay as history (see `trips.group_id`'s `ON DELETE RESTRICT` in
`app/models/trip.py`, which also stops a group from being deleted while
trip history still references it).

## GPS locations

Permanent historical GPS storage — no Redis/WebSocket real-time layer yet
(that's Phase 6). Every point belongs to a trip and is only ever accepted
while that trip is `ACTIVE`.

| Endpoint | Who | Effect |
|---|---|---|
| `POST /api/v1/trips/{trip_id}/locations` | active member of the trip's group, trip must be `ACTIVE` | stores one GPS reading |
| `GET /api/v1/trips/{trip_id}/locations` | active member of the trip's group (any trip status) | chronological GPS history |

**Fields** — `latitude`/`longitude` are the only required fields.

| Field | Unit | Notes |
|---|---|---|
| `latitude`, `longitude` | decimal degrees | -90..90 / -180..180 |
| `accuracy` | meters | optional, must be >= 0 |
| `speed` | meters/second | optional, device-reported — never derived from coordinates in this phase |
| `heading` | degrees, 0 <= h < 360 | optional; 0=N, 90=E, 180=S, 270=W — never calculated in this phase |
| `recorded_at` | UTC timestamp | when the *device* captured the point; defaults to server time if omitted |
| `created_at` | UTC timestamp | when the *backend* stored it — always server-assigned |

`recorded_at` — not `created_at` — is what the history endpoint orders by,
since mobile networks can deliver points out of order. A `recorded_at` more
than 5 minutes in the future is rejected as `400 INVALID_TIMESTAMP` (normal
clock drift is tolerated; a broken device clock is not). Naive timestamps
are treated as UTC.

**Storage**: coordinates are stored twice — as plain `latitude`/`longitude`
floats (what the API returns) and as a PostGIS `GEOGRAPHY(POINT, 4326)`
(`POINT(longitude latitude)` — longitude first) for future geospatial
queries. The raw PostGIS value is never serialized back to the client.

**Trust boundary**: `LocationCreate` has no `id`/`trip_id`/`group_id`/
`user_id`/`created_at` fields — `trip_id` comes from the URL, `group_id`
from `trip.group_id`, `user_id` from the verified JWT. A trip that doesn't
exist and a trip whose group the caller isn't an active member of both
return the same `404 TRIP_NOT_FOUND` (same existence-hiding pattern as
trips/groups).

**History filtering & pagination**: `GET .../locations` accepts `from`,
`to`, `user_id`, `limit` (default 500, max 5000), and `cursor` (an ISO
timestamp — returns only points with `recorded_at` strictly after it).
To page forward, pass the `recorded_at` of the last point you received as
the next request's `cursor`. Results are always scoped to the one trip in
the URL, so an unrelated `user_id` just returns an empty list rather than
leaking another group's data.

**Rate limiting on this REST endpoint**: still not implemented (see the
WebSocket's own per-connection limiter below, which is what mobile clients
are actually expected to use for frequent updates during a trip).

## Live tracking (WebSocket + Redis)

`POST/GET /trips/{trip_id}/locations` (above) is the durable record.
`WS /api/v1/ws/trips/{trip_id}` is the real-time layer on top of it — every
valid update still lands in `location_history`, but connected group
members also see it arrive within milliseconds via Redis Pub/Sub, without
polling.

**Redis vs. Supabase — the split is strict and intentional:**

| | Redis | Supabase/Postgres |
|---|---|---|
| What | current location, presence, Pub/Sub events | profiles, groups, memberships, trips, **location_history** |
| Lifetime | seconds (TTL'd) | forever |
| Source of truth for | "where is everyone *right now*" | everyone else — including group membership, which Redis never decides |

Redis is disposable: if it's flushed or restarted, live tracking just
resets (a client's next update repopulates it) — no historical data is
ever at risk, because none of it lives there.

### Redis data model

```
trip:{trip_id}:user:{user_id}:location   STRING (JSON), TTL = LIVE_LOCATION_TTL_SECONDS
trip:{trip_id}:users                     SET of user ids with a live location
trip:{trip_id}:presence:{user_id}        STRING "1", TTL = PRESENCE_TTL_SECONDS — existence = ONLINE
trip:{trip_id}:events                    Pub/Sub channel — every FastAPI instance with a local
                                          connection for this trip subscribes to it
```

All key/channel names are built in `app/core/redis_keys.py` — nowhere
else in the codebase hand-builds one.

### Authentication

Browsers can't set custom WebSocket headers, so the token travels as a
query parameter:

```
wss://api.rally.app/api/v1/ws/trips/{trip_id}?token=<supabase_access_token>
```

This is weaker than an `Authorization` header (the token can end up in
server access logs or browser history) — mitigated by requiring `wss://`
(TLS) in production and by the token's own short Supabase-issued
lifetime. The token is never logged by this endpoint.

The connection is **accepted first**, then authenticated/authorized —
deliberately, so a rejected client receives a structured JSON `error`
frame explaining exactly why (`UNAUTHORIZED` / `TRIP_NOT_FOUND` /
`NOT_A_MEMBER` / `TRIP_NOT_ACTIVE`) before the socket closes with a
matching `44xx` code, rather than just a bare close code a browser barely
surfaces.

### Client → server messages

```json
{"type": "location_update", "data": {
  "latitude": 22.7196, "longitude": 75.8577,
  "accuracy": 8.5, "speed": 12.4, "heading": 180,
  "recorded_at": "2026-08-30T10:00:00Z"
}}
```
```json
{"type": "heartbeat"}
```

`latitude`/`longitude` are required; everything else is optional, same
validation rules as the REST endpoint (`app/schemas/location.py`).
`user_id`/`trip_id`/`group_id` are never accepted from the client — the
schema has no such fields, and the server always uses the authenticated
connection's own identity.

### Server → client messages

```json
{"type": "trip_state", "data": {"trip_id": "...", "members": [
  {"user_id": "...", "name": "Keshav", "role": "LEADER",
   "latitude": 22.7196, "longitude": 75.8577, "speed": 12.4, "heading": 180,
   "accuracy": 8.5, "recorded_at": "...", "status": "ONLINE"}
]}}
```
Sent once, immediately after connecting — the group's active membership
(Supabase, authoritative) with each member's current location/presence
(Redis) layered on top.

```json
{"type": "location_update", "data": {
  "user_id": "...", "latitude": 22.7196, "longitude": 75.8577,
  "accuracy": 8.5, "speed": 12.4, "heading": 180,
  "recorded_at": "...", "updated_at": "..."
}}
```
Broadcast to every *other* connected member — never the client's raw
message, always rebuilt server-side.

```json
{"type": "location_ack", "data": {"recorded_at": "...", "accepted": true}}
```
Sent only to the sender. `accepted: false` means the update was received
but a real storage failure prevented it from being durably saved (never
silently lied about) — distinct from a rejected/invalid update, which
comes back as an `error` frame instead.

```json
{"type": "presence_update", "data": {"user_id": "...", "status": "ONLINE"}}
```
Published on a user's first connection and on their last disconnection
(multiple tabs/devices for one user are tracked — the second tab
connecting doesn't re-announce someone already online, and the first tab
closing doesn't announce them offline while the second is still up).

```json
{"type": "trip_ended", "data": {"trip_id": "...", "status": "COMPLETED"}}
```
Sent when the trip is ended/cancelled via the REST API; every instance
with local connections for that trip closes them right after.

```json
{"type": "heartbeat_ack", "data": {"server_time": "..."}}
```

```json
{"type": "error", "data": {"code": "INVALID_LOCATION", "message": "..."}}
```
Codes: `UNAUTHORIZED`, `TRIP_NOT_FOUND`, `TRIP_NOT_ACTIVE`,
`NOT_A_MEMBER`, `INVALID_MESSAGE`, `INVALID_LOCATION`, `RATE_LIMITED`,
`INTERNAL_ERROR`. Never a stack trace or raw exception.

### Performance / abuse protection

- Trip/membership authorization is checked once at connect time and
  cached on the connection (`TripConnectionContext`) — not re-queried per
  message. "Is the trip still ACTIVE" is tracked as a local flag, flipped
  by either a `trip_ended` broadcast or the persistence layer itself
  discovering the trip is no longer active — not a DB poll per message.
- `MAX_LOCATION_UPDATES_PER_SECOND` (default 5) is a per-connection
  sliding-window limiter — generous enough that normal GPS tracking never
  trips it.
- `WS_MAX_MESSAGE_BYTES` (default 8192) rejects oversized frames before
  they're even parsed.
- Cross-instance broadcast goes through Redis Pub/Sub, not an in-memory
  dict — one subscriber task per trip per process (started on its first
  local connection, stopped on its last), not one Redis connection per
  message.

## Intelligence engine (app/intelligence/)

Turns raw GPS into group-level detections — falling behind, group
separation, isolated member, unexpected stop, speed anomaly, and the
positive "moving together" state. **Detects, never alerts** — this phase
only records what's happening; a later Alert Engine decides what to do
about it.

**Detection, not prediction**: every detector is a plain threshold +
persistence check (see `app/intelligence/thresholds.py` for every default),
never ML. A condition must hold continuously for its configured duration
— tracked via a small Redis timer per `(trip, event_type, subject)` — 
before it's ever recorded, so one noisy GPS point can't create an event.

**Movement classification** (`app/intelligence/movement.py`): each member
is MOVING, STOPPED, STALE (online but no fresh GPS), or OFFLINE (no
WebSocket presence) — STALE and OFFLINE are deliberately distinct signals.
Entering STOPPED requires the low-speed reading to persist for
`STOP_DURATION_SECONDS`; resuming MOVING is immediate.

**Persisted events** (`intelligence_events` table): `resolved_at IS NULL`
= active, matching the same lifecycle pattern as `alerts`/`sos_events`. A
partial unique index on `(trip_id, event_type, user_id) WHERE resolved_at
IS NULL` — the same technique as trips' one-active-trip rule — guarantees
two concurrent evaluations can never create duplicate active events for
the same subject, regardless of application-level races.

**Background evaluator** (`app/intelligence/worker.py`): one centralized
loop, started from `app.main`'s lifespan, re-evaluating every currently
ACTIVE trip every `INTELLIGENCE_EVALUATION_INTERVAL_SECONDS` (default 3s).
A per-trip Redis lock (`SET NX PX`) means a second worker instance racing
on the same trip skips it rather than double-evaluating. Designed so this
loop body can later move to Celery/RQ/Redis Streams without touching the
detection logic itself.

**APIs**: `GET /trips/{trip_id}/intelligence` (current calculated state —
Redis live data plus the same detector logic the worker uses, never a
`location_history` scan) and `GET /trips/{trip_id}/intelligence-events`
(historical detections, filterable by `event_type`/`severity`/`user_id`/
`active_only`/`from`/`to`/`limit`). Both require active trip membership,
same authorization as every other trip-scoped endpoint.

**WebSocket**: an `intelligence_event` frame is published (via the same
Redis Pub/Sub mechanism as `location_update`/`presence_update`) whenever a
detector's result actually changes — created or resolved, never on an
unchanged "still active" tick.

```json
{"type": "intelligence_event", "data": {
  "event_type": "FALLING_BEHIND", "severity": "WARNING",
  "user_id": "...", "related_user_id": null,
  "detected_at": "...", "resolved_at": null,
  "metadata": {"distance_meters": 650, "threshold_meters": 500, "duration_seconds": 124.0}
}}
```

## Alerts + SOS (app/alerts/, app/sos/)

**Alert Engine** (`app/alerts/`): consumes intelligence_events, never
produces them itself — detectors have no idea alerts exist. Policy
(`app/alerts/policies.py`) maps each WARNING-tier `IntelligenceEventType`
(FALLING_BEHIND, GROUP_SEPARATION, ISOLATED_MEMBER, UNEXPECTED_STOP,
SPEED_ANOMALY) to an `AlertType`/title/message template; INFO-level states
(MOVING_TOGETHER, STOPPED, MOVING) have no policy and never become alerts.
`status`: `ACTIVE → ACKNOWLEDGED → RESOLVED`, or directly `ACTIVE →
RESOLVED` (e.g. auto-resolved the moment the underlying intelligence
event resolves). One alert per intelligence event, guaranteed by a
partial unique index on `alerts(event_id) WHERE resolved_at IS NULL` —
the same technique as trips'/intelligence_events' own dedup rules — so a
condition staying active for 5 minutes of evaluation ticks produces
exactly one alert, updated in place, not one per tick.

| Endpoint | Who |
|---|---|
| `GET /trips/{trip_id}/alerts` | active trip member, filterable |
| `GET /trips/{trip_id}/alerts/active` | active trip member |
| `GET /alerts/{alert_id}` | active member of the alert's group |
| `POST /alerts/{alert_id}/acknowledge` | active member of the alert's group |
| `POST /alerts/{alert_id}/resolve` | active member of the alert's group |

**SOS** (`app/sos/`): explicitly user-triggered, never generated from an
intelligence event or an alert — a completely separate system. PostgreSQL
(`sos_events`) is written first and is the permanent record; a disposable
Redis mirror (`trip:{trip_id}:sos:{sos_id}`, **no TTL**) just makes "is
there an active emergency" a fast Redis read instead of a query. The
trigger location is captured once and is immutable — nothing overwrites
it later. `status`: `ACTIVE → ACKNOWLEDGED → RESOLVED`, or `CANCELLED`
(only by the original triggering user). **SOS safety rule**: a WebSocket
disconnect, stale GPS, a user going offline, or the Redis mirror
disappearing must never resolve or cancel an SOS — its lifecycle is
governed exclusively by an explicit acknowledge/resolve/cancel call.

| Endpoint | Who |
|---|---|
| `POST /trips/{trip_id}/sos` | active member of an ACTIVE trip |
| `GET /trips/{trip_id}/sos` | active trip member |
| `GET /trips/{trip_id}/sos/active` | active trip member |
| `POST /sos/{sos_id}/acknowledge` | active member of the SOS's group |
| `POST /sos/{sos_id}/resolve` | active member of the SOS's group |
| `POST /sos/{sos_id}/cancel` | **only** the user who triggered it |

**WebSocket**: `alert` / `alert_updated` / `sos` / `sos_updated`, all via
the same Redis Pub/Sub mechanism every other broadcast in this backend
uses.

```json
{"type": "alert", "data": {"id": "...", "alert_type": "FALLING_BEHIND",
  "severity": "WARNING", "title": "Member falling behind",
  "message": "A group member is falling behind (650m from the group).",
  "user_id": "...", "created_at": "..."}}
```
```json
{"type": "sos", "data": {"id": "...", "trip_id": "...", "user_id": "...",
  "latitude": 22.7196, "longitude": 75.8577, "accuracy": 8.5,
  "message": "Need help", "status": "ACTIVE", "triggered_at": "..."}}
```

## Route intelligence (app/route/)

Extends the Phase 7 intelligence engine — it doesn't replace it. A trip's
group-relationship intelligence (falling behind, group separation,
isolated member, unexpected stop, speed anomaly, moving together) is
computed exactly as before; route intelligence layers a second, optional
question on top: *is the group actually following the planned route?* A
trip with no route (or a route that isn't ACTIVE yet) evaluates precisely
as it did before this phase existed.

**Route model** (`routes` table, `app/models/route.py`): one route per
trip (`trip_id` is UNIQUE). GPS updates never modify a route's geometry —
only an explicit leader replace (while still `PLANNED`) or a trip-
lifecycle transition changes it. `geometry` is a real PostGIS
`LINESTRING(4326)` column; `coordinates` is a JSONB mirror of the exact
same points in **GeoJSON order, `[longitude, latitude]`** — the opposite
of the `(latitude, longitude)` order used almost everywhere else in this
API, and what `app/route/matcher.py` actually reads for live matching.
`distance_meters` is always server-calculated (a Haversine sum over
`coordinates`, mathematically equivalent to `ST_Length(geography)`) —
never trusted from the client.

`status` lifecycle: `PLANNED → ACTIVE → COMPLETED`, or `PLANNED →
CANCELLED`. Hooked into the existing trip endpoints
(`app/api/trips.py`), not `trip_service.py` itself: starting a trip
activates its route, ending one completes it, cancelling one (only
possible while the trip is still `CREATED`) cancels its route too. There
is no route versioning — "replacing" a `PLANNED` route updates the same
row in place.

**Matching, in pure Python** (`app/route/matcher.py`): every intelligence
tick projects each member's live position onto the route's geometry using
Shapely (per-segment planar nearest-point projection), then converts that
into real-world meters via the same Haversine helper the group-
intelligence detectors use. Deliberately not a PostGIS round trip per GPS
update — a live trip matches every member on every evaluation tick against
geometry that never changes mid-trip, so loading it once and matching in
memory is both cheaper and (in an environment with no live PostGIS
connection to round-trip to) the only thing actually testable here.

**Progress states** (`app/route/progress.py`): `ON_ROUTE`, `OFF_ROUTE`
(beyond `OFF_ROUTE_THRESHOLD_METERS` from the line), `NEAR_DESTINATION`
(within a derived multiple of `ARRIVAL_THRESHOLD_METERS` of the
destination — not independently configurable), and `ARRIVED`. `ARRIVED`
is the one state that's debounced — sustained proximity for
`ARRIVAL_DURATION_SECONDS` — via the same Redis condition-timer shape
`app/intelligence/detectors.py` uses, so a member skimming the threshold
doesn't flap in and out of "arrived." A trip counts as arrived only once
every member with a *usable* live location (online, GPS no older than
`ROUTE_PROGRESS_STALE_SECONDS`) is confirmed `ARRIVED` — offline/stale
members are excluded from that check, not treated as blocking it forever.
Group progress is the **median** (not mean) of eligible members'
`route_fraction`, so one outlier can't single-handedly skew it.

**ETA** (`app/route/eta.py`): baseline-only in this phase — no traffic, no
live-speed averaging, no historical pace model. `EtaService.calculate_eta`
prefers the route's own declared `distance_meters` /
`estimated_duration_seconds` (as an average speed) and otherwise falls
back to `BASELINE_ROUTE_SPEED_MPS`; it already accepts (but doesn't yet
use) a live speed argument, so a future phase can wire in a real speed
source without any caller changing.

**New intelligence event**: `ROUTE_DEVIATION` — the one route-related
signal that persists as a real `intelligence_events` row (every other
route state above is an ephemeral progress label, not an event). Gated by
`ROUTE_DEVIATION_DURATION_SECONDS` via the exact same persistence-timer
detector shape as every Phase 7 detector — a single noisy off-route
reading never creates it, and returning to the route resolves it. It flows
through the existing Phase 7 → Phase 8 pipeline unchanged: the same
`intelligence_event` WebSocket frame, and (via a new entry in
`app/alerts/policies.py`) the same `alert` frame every other WARNING-tier
detection produces — there is no separate alert path for route events.

**APIs**:

| Endpoint | Who |
|---|---|
| `POST /trips/{trip_id}/route` | **group leader only**, trip must be `CREATED` |
| `GET /trips/{trip_id}/route` | active trip member |
| `GET /trips/{trip_id}/route/progress` | active trip member; 409 unless trip + route are both `ACTIVE` |

**WebSocket**: a continuous `route_progress` frame every evaluation tick a
trip has an ACTIVE route (unlike `intelligence_event`, sent regardless of
whether anything changed — it's a live readout, not a discrete event),
plus a `route_deviation` frame specifically on `ROUTE_DEVIATION`
created/resolved transitions (in addition to, not instead of, the generic
`intelligence_event` frame that already carries it).

```json
{"type": "route_progress", "data": {
  "trip_id": "...", "route_id": "...", "group_route_fraction": 0.42,
  "trip_arrived": false,
  "members": [{"user_id": "...", "route_state": "ON_ROUTE", "route_fraction": 0.42,
    "distance_remaining_meters": 3210.0, "eta_seconds": 290.0}]
}}
```
```json
{"type": "route_deviation", "data": {
  "user_id": "...", "distance_from_route_meters": 180.0,
  "status": "DEVIATED", "detected_at": "..."
}}
```

## Analytics + trip history + dashboard (app/analytics/)

Turns everything the earlier phases already recorded — trips, routes,
location_history, intelligence_events, alerts, sos_events — into the
aggregated, dashboard-ready numbers the frontend needs. **Read-only**:
nothing in `app/analytics/` ever writes to those tables (the one
exception, `trip_analytics_snapshots`, is itself a derived, disposable
cache — see Snapshot below).

**Data sources, split by module** (`app/analytics/`):
- `queries.py` — the only place distance/duration math actually lives:
  pure functions over already-fetched rows, no DB/Redis inside them, so
  they're unit-tested directly.
- `trip_analytics.py`, `member_analytics.py`, `route_analytics.py`,
  `safety_analytics.py`, `timeline.py` — one module per headline
  endpoint, each composing `queries.py` plus the *existing* services
  (`app/route/service.py`, `app/alerts/service.py`, `app/sos/service.py`,
  `app/intelligence/events.py`) rather than re-querying those tables a
  second, possibly-diverging way.
- `dashboard.py` — composes all of the above plus live Redis state for
  the one endpoint the frontend should actually poll.
- `snapshot.py`, `history.py` — completed-trip snapshot generation and
  the two trip-history listings.

**Distance traveled**: consecutive-GPS-point Haversine (the same approach
`app/intelligence/distance.py` and `app/route/matcher.py` already use),
not straight-line origin-to-destination and not the planned route's own
length. Two filters keep bad GPS from inflating it (`GPS_DISTANCE_FILTERING`):
a point whose reported `accuracy` is worse than `MIN_USABLE_ACCURACY_METERS`
is dropped entirely before segments are even formed, and a segment
implying a speed above `MAX_ANALYTICS_SPEED_MPS` (an impossible jump) is
skipped with the anchor left in place, so one corrupted fix can't also
poison its neighbor. `location_history` itself is never modified by any
of this.

**Group distance ("how far did the group travel")**: never the sum of
every member's own distance — that would double/triple-count one shared
journey. Instead: the group **leader's** own distance when they have GPS
data, falling back to the **median** across whichever members do
(`queries.pick_representative_value`) — deterministic, and resistant to
one outlier the way a mean isn't. The exact same "leader, else median"
rule is reused for the group's route-completion percentage.

**Route completion**: `route_fraction` from matching each member's
*last* GPS point against the persisted route geometry
(`app/route/matcher.py`, reused as-is — not re-derived), never
`distance(origin, current) / distance(origin, destination)`, which is
wrong for anything but a straight line.

**Movement analytics (moving/stopped duration)**: derived from Phase 7's
own persisted MOVING/STOPPED `intelligence_events` transitions — real
historical rows, not invented. A member with zero such rows (e.g. the
intelligence worker never evaluated their trip) gets
`movement_duration_available: false` and both durations `null`, never a
fabricated `0`. STALE/OFFLINE time has no historical record anywhere in
this system and is never reported as its own metric.

**APIs**:

| Endpoint | Notes |
|---|---|
| `GET /trips/{trip_id}/analytics` | duration, distance, route completion, alert/SOS/deviation counts — snapshot-served when COMPLETED and a snapshot exists |
| `GET /trips/{trip_id}/analytics/members` | the same, broken out per member |
| `GET /trips/{trip_id}/analytics/route` | completion %, deviation counts, average/max deviation distance |
| `GET /trips/{trip_id}/analytics/safety` | alert totals (by severity + by type), SOS totals, anomaly intelligence-event totals |
| `GET /trips/{trip_id}/timeline` | every meaningful trip/route/alert/SOS/intelligence-anomaly moment, ascending by timestamp |
| `GET /trips/{trip_id}/dashboard` | the primary frontend endpoint — see below |
| `GET /users/me/trips` | the authenticated user's trip history across every group they're in |
| `GET /groups/{group_id}/trips` | one group's trip history (replaces the old unpaginated list shape) |

All eight require active trip/group membership, exactly like every other
endpoint in this API — never another group's data.

**Dashboard** (`GET /trips/{trip_id}/dashboard`): the one endpoint the
frontend should actually poll instead of assembling a dashboard from
several other calls. For an **ACTIVE** trip ("live" mode): combines
`app/intelligence/engine.py::compute_current_state` (Redis + group
relationships), `app/route/service.py::get_live_route_progress` (Redis +
route matching) for the route/member `route_state`/progress fields, and
DB-backed active-alert/active-SOS counts. If Redis is configured but
unreachable, this degrades gracefully — the Redis-only fields (online/
moving/stopped counts, live route progress) become `null` rather than
failing the whole request. For any other status ("historical" mode):
entirely PostgreSQL — Redis is never called at all, so a completed trip's
dashboard works with Redis fully down.

**Trip history**: `GET /users/me/trips` and `GET /groups/{group_id}/trips`
both support `status`, `from`, `to`, `limit` (default 20, max 100), and
`offset`, returning `{items, total, limit, offset}`. "Participated"/
"belongs to this group" is scoped the same way every other trip-scoped
endpoint in this API scopes membership — a currently ACTIVE member of the
trip's group; a user who has since left stops seeing that group's
history, consistent with `require_trip_member`/`require_group_member`
everywhere else. `/users/me/trips` always derives the user id from the
verified token — there is no `user_id` parameter to spoof another user's
history with.

**Snapshot** (`trip_analytics_snapshots`, generated in
`app/api/trips.py::end_trip_endpoint` right after a trip completes): a
frozen copy of that trip's headline numbers, so `GET .../analytics` and
the history listings don't re-scan `location_history` on every request
for a trip that will never change again. `trip_id` is UNIQUE at the
database level — at most one snapshot per trip, and a retried/concurrent
generation reuses the existing row rather than erroring or duplicating.
Snapshot generation can **never** fail trip completion itself: any error
is logged and swallowed (`generate_snapshot_safely`). The original
tables remain the source of truth; this table is entirely derived and,
in principle, regenerable from them.

**Redis vs PostgreSQL** — the one rule every module above follows:

| | Redis | PostgreSQL |
|---|---|---|
| ACTIVE trip | current location, online/moving/stopped counts, live route progress | active alerts/SOS (always DB — Phase 8 never used Redis as the source of truth for those) |
| COMPLETED/CANCELLED trip | never touched | everything — distance, route completion, alerts, SOS, timeline, snapshot |

**Zero vs null** — the contract this whole phase exists to enforce:
`0`/`0.0` means the count or measurement is genuinely zero (no alerts
happened; SOS was never triggered). `null` means it could not be
calculated (no GPS data at all → `distance_traveled_meters: null`; no
planned route → every `route_*` field `null`, plus `route_available:
false` so the frontend never has to guess why). Every schema in
`app/schemas/analytics.py` documents which of its fields can be `null`
and why, field by field.

**Performance**: distance/duration math pulls only the columns it needs
(never full rows/geometry) via the existing `location_history` composite
indexes, in one query per trip rather than one per member. Alerts/SOS/
intelligence-event aggregation reuses the existing `list_*()` service
functions (already indexed by `trip_id`) and aggregates in Python at the
row counts one trip realistically produces, rather than adding parallel
bespoke `GROUP BY` queries that could drift out of sync with what those
services themselves consider "active"/"resolved." A COMPLETED trip's
distance in a history listing prefers its snapshot (an O(1) read) over
re-scanning `location_history` on every page of every history request. A
new composite index, `ix_trips_group_created` (`group_id, created_at`),
serves the group-trip-history query's filter+sort pattern directly.

## Production hardening + observability (Phase 11)

Everything in this section is additive protection/visibility layered on
top of the working backend from Phases 1–10 — no existing endpoint's
behavior changes for a normal, well-formed, under-the-limit request.

**Configuration validation** (`app/core/config.py`): `ENVIRONMENT` is
`"development"` (default), `"test"`, or `"production"`. Setting
`ENVIRONMENT=production` makes `DATABASE_URL`, `REDIS_URL`,
`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and
`JWT_SECRET` all mandatory — the process fails at import time with a
clear `ValueError` listing exactly what's missing, rather than starting
in a half-configured state. Development/test are unaffected.

**Rate limiting** (`app/core/rate_limit.py`): Redis-backed fixed-window
counters (`INCR` + `EXPIRE`), keyed by `user:{user_id}` when the caller is
authenticated, `ip:{client_ip}` otherwise. **Fails open** — a Redis
outage or misconfiguration never blocks real traffic, only logs a
warning; rate limiting is a best-effort abuse guard, not a control this
API's availability depends on.

| Scope | Limit (default) | Applied to |
|---|---|---|
| `api` (general) | `GENERAL_API_RATE_LIMIT_PER_MINUTE` (100/min) | every request, via `GeneralRateLimitMiddleware` |
| `auth` | `AUTH_RATE_LIMIT_PER_MINUTE` (10/min) | `GET /auth/me` |
| `join_group` | `JOIN_GROUP_RATE_LIMIT_PER_MINUTE` (10/min) | `POST /groups/join` — the one endpoint guessing a secret (the join code) |
| `sos` | `SOS_RATE_LIMIT_PER_MINUTE` (5/min) | `POST /trips/{trip_id}/sos` |
| `location` | derived from `MAX_LOCATION_UPDATES_PER_SECOND` | `POST /trips/{trip_id}/locations` |

A 429 always has the same envelope as every other error (see below), plus
`retry_after_seconds` in the `error` object and a `Retry-After` header.
SOS is deliberately **not** the most aggressively limited endpoint — the
real protection against a duplicate/retried trigger is
`sos_service.trigger_sos`'s own idempotency check (an already-ACTIVE SOS
for that user+trip is returned as-is, never duplicated — see Part 7
below), so this limit only guards against a distinct trigger/cancel/
retrigger abuse loop and never blocks a first, genuine emergency call.
**Join-code protection**: a removed member re-attempting to join gets the
same generic "cannot join this group" 403 as an inactive group, not a
message confirming they were specifically removed (`app/services/
group_service.py::join_group`).

**Idempotency** (Part 7): SOS is the one operation this phase protects
explicitly, per its own "do not add idempotency blindly" instruction —
`trigger_sos` checks for an existing ACTIVE/ACKNOWLEDGED SOS for the same
(trip, user) before creating a new row, returning the existing one
instead. Trip start/end/route creation are already safe against retries
by construction (the existing state-machine `_require_transition` /
`INVALID_TRIP_STATE` 409 checks from Phases 4 and 9 reject a duplicate
attempt outright — retrying a "start" on an already-ACTIVE trip can never
create a second trip or route).

**WebSocket hardening** (`app/api/websocket.py`, `app/websocket/
{manager,handlers}.py`): a per-user connection limit
(`MAX_WS_CONNECTIONS_PER_USER`, default 5) rejects a new connection
outright once reached (never silently closes an existing one — for a
live-tracking safety app, disturbing some other, possibly still-in-use
tab/device is the more dangerous policy). A general per-connection
message-rate limit (`WEBSOCKET_MESSAGES_PER_SECOND`, a one-second-window
counter tolerant of a legitimate quick burst of different message types)
sits alongside the existing `MAX_LOCATION_UPDATES_PER_SECOND` limit that's
still specific to `location_update`; a connection that stays over the
general limit for `WEBSOCKET_FLOOD_DISCONNECT_THRESHOLD` consecutive
messages is disconnected outright, not throttled forever. The Redis
Pub/Sub subscriber loop behind cross-instance broadcast now reconnects
with bounded exponential backoff (up to `REDIS_RETRY_LIMIT` attempts,
capped at `REDIS_RETRY_MAX_BACKOFF_SECONDS`) instead of the task simply
dying the first time the Redis connection drops.

**Redis resilience** (`app/core/redis.py`): the client is built with
`socket_connect_timeout`/`socket_timeout` (`REDIS_CONNECT_TIMEOUT_SECONDS`
/ `REDIS_SOCKET_TIMEOUT_SECONDS`) and `retry_on_timeout=True`, so no
command can hang indefinitely — every existing "Redis unavailable"
fallback path from earlier phases (live tracking degrades, historical
data/alerts/SOS are unaffected) is unchanged, just bounded in time now.

**Database resilience** (`app/core/database.py`): a real bounded
connection pool (`DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`,
`DATABASE_POOL_TIMEOUT_SECONDS`, `DATABASE_POOL_RECYCLE_SECONDS`) instead
of one connection per request; `pool_pre_ping` (already present since
Phase 1) plus `pool_recycle` together handle a managed Postgres provider
silently dropping idle connections. `close_database()` disposes the pool
cleanly on shutdown.

**Structured logging + request IDs** (`app/core/middleware.py`):
`RequestIDMiddleware` generates (or reuses a well-formed client-supplied)
`X-Request-ID`, returns it as a response header, and logs one line per
request — `request_id method path status_code duration_ms`, nothing else
(never headers, query strings, bodies, or GPS coordinates). Every error
response's `error` object also carries the same `request_id`, so a
user-reported failure maps directly to server log lines. `LOG_LEVEL`
(default `INFO`) controls verbosity; production never runs at `DEBUG` by
default even if left unset.

**Standard error envelope** — unchanged in shape from earlier phases,
additive only:

```json
{"success": false, "error": {
  "code": "RATE_LIMITED", "message": "Too many requests",
  "request_id": "...", "retry_after_seconds": 10
}}
```

**Health checks** (`app/api/health.py`): `GET /health` is **liveness** —
"is the process alive at all?" — and never fails (200) just because a
dependency is down, only reports it. `GET /health/ready` is **readiness**
— checks PostgreSQL and (when configured) Redis, returns 503 the instant
either is actually unavailable, for a load balancer/orchestrator to stop
routing traffic here until it recovers. Never conflate the two: restarting
an instance that's alive-but-not-ready doesn't fix a downstream outage.

**Metrics** (`app/core/metrics.py`, `GET /metrics`): a small dependency-
free in-process registry (counters/gauges/simple count+sum
observations) — request counts/latency by method+route-template,
error/429 counts, WebSocket connect/disconnect/active-connection counts,
Redis error/reconnect counts, intelligence-tick error counts and
per-trip evaluation duration, alerts/intelligence-events
generated/resolved, SOS triggered/resolved. `?format=prometheus` (default,
plain text-exposition format) or `?format=json`. Exposes **no** personal
data — no GPS, no user/trip ids, no SOS messages, no tokens; labels are a
small fixed vocabulary (HTTP method, status code, route template, event
type) only.

**CORS + security headers**: `CORS_ALLOWED_ORIGINS` (preferred) or
`FRONTEND_URL` (fallback) — never a wildcard, since this API sends
credentials. Every response also carries `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, and `Referrer-Policy:
strict-origin-when-cross-origin` (`SecurityHeadersMiddleware`).

**Request body size** (`app/core/middleware.py::MaxBodySizeMiddleware`):
a request whose declared `Content-Length` exceeds
`MAX_REQUEST_BODY_BYTES` (default 1MB — generous headroom for every JSON
body this API accepts) is rejected with 413 before the body is ever read.

**API docs toggle**: `ENABLE_DOCS` (default `true`) — set `false` to
remove `/docs`, `/redoc`, and the raw OpenAPI schema entirely (not just
hide a link to them) in a deployment that shouldn't advertise its API
surface publicly.

**Graceful shutdown** (`app.main`'s lifespan): stop the intelligence
worker first, then close every live WebSocket connection
(`manager.close_all()`, close code 1001), then release Redis, then
dispose the database connection pool — in that order, so nothing is
still trying to use a resource that's already been torn down.

**Worker supervision** (`app/intelligence/worker.py`): the background
evaluation loop now wraps each tick in its own try/except — a failure
logs (never a bare `except: pass`), increments a metric, and the loop
keeps running on schedule. Previously an exception `run_evaluation_tick()`
didn't already catch internally (e.g. failing to open a new DB session)
would have silently killed the entire background task for the rest of
the process's life.

**Data retention**: `LOCATION_RETENTION_DAYS` is documented and
available in config but **not activated** — no scheduled job reads it in
this phase. `location_history`/`intelligence_events`/`alerts`/
`sos_events` are never automatically deleted.

## Advanced features + demo mode (Phase 12)

Eight additions on top of the working backend from Phases 1–11 — nothing
here changes how any earlier phase behaves; every new capability composes
existing services rather than duplicating their logic.

### Trip replay (`app/analytics/replay.py`)

`GET /trips/{trip_id}/replay?interval_seconds=N` — a compact, evenly-
sampled timeline instead of every raw GPS point. Global timestamps
`interval_seconds` apart (clamped to `REPLAY_MIN_INTERVAL_SECONDS`..
`REPLAY_MAX_INTERVAL_SECONDS`, default `REPLAY_DEFAULT_INTERVAL_SECONDS`)
span the trip's actual GPS data range; at each one, every member's most
recent point at-or-before that time is carried forward (never
interpolated — a member with no point yet simply isn't in that frame).
Movement state per frame comes from Phase 7's persisted MOVING/STOPPED
transition history, never guessed from raw speed a second way; route
progress per frame is computed by matching the carried-forward point
against the route's stored geometry (Phase 9's own matcher). `events`
reuses `GET /trips/{trip_id}/timeline` wholesale, so replay and timeline
can never disagree about what happened. `REPLAY_MAX_FRAMES` is a hard
ceiling — a request that would produce more frames than that gets a
coarser effective interval instead, deterministically, never a truncated
ending.

### Advanced ETA (`app/route/eta.py`)

`EtaService.calculate_eta()` now actually uses a member's live GPS speed
when it's usable — faster than `STOP_SPEED_MPS` (not "basically
stopped," which would imply an absurd ETA if divided into) and no faster
than `MAX_REASONABLE_SPEED_MPS` (not a sensor glitch) — falling back to
the route's own declared average speed, then `BASELINE_ROUTE_SPEED_MPS`,
exactly as before when no usable speed exists. `eta_available` is now
explicit on the result: `False` only when nothing usable is left to fall
back to, and `eta_seconds` is `None` in that case — never `0`, which is
reserved for a genuinely zero remaining distance.

`EtaService.calculate_group_eta()` is new: "when is the group likely to
finish together," built from the **median** remaining distance across
members with a route match (a straggler pulls this toward "later," the
correct behavior for a group figure) and the **median** speed among
currently-moving members only — stopped/offline members don't drag the
representative pace toward zero, they simply don't contribute a speed
sample. Deliberately never the fastest member's own ETA. Falls back the
same way a single member's ETA does if the whole group is stopped.

### Smart risk score (`app/risk/`)

`GET /trips/{trip_id}/risk` — a deterministic, explainable 0–100 safety
score computed by `RiskService.calculate_trip_risk()` from real,
already-persisted signals only (active SOS, active alerts, active
WARNING-tier intelligence events) — never fabricated. Same input always
produces the same score: no randomness, no ML, no time-of-day weighting.

| Score | Level |
|---|---|
| 0–`RISK_LOW_MAX` (30) | LOW |
| `RISK_MEDIUM_MAX` (60) and below | MEDIUM |
| `RISK_HIGH_MAX` (80) and below | HIGH |
| above `RISK_HIGH_MAX` | CRITICAL |

Every point of score comes from a named, weighted factor (`RISK_WEIGHT_*`
settings — all configurable, none hardcoded in the calculation logic):
active SOS, an unresolved critical alert, group separation, an isolated
member, falling behind, route deviation, an unexpected stop, a speed
anomaly, and (only when the caller has live online/member counts — the
one DB+Redis-optional factor, skipped rather than fabricated when those
aren't available) a low active-member ratio. Multiple simultaneous
falling-behind members produce one factor with a count in its
description, not one factor per member. The response always explains
itself — every factor carries `type`, `impact`, and a plain-language
`description` generated from the event type, never an LLM.

### Trip insights (`app/analytics/insights.py`)

`GET /trips/{trip_id}/insights` — plain, deterministic sentences built
directly from the same aggregated numbers `GET /trips/{trip_id}/analytics`
already computes (reused, never re-derived a second way) — no LLM, no
narrative generation. A highlight is only ever added when its underlying
number actually exists (route completion, distance, duration, deviations,
alerts, SOS, member participation); missing data simply produces fewer
highlights, never a vague or invented one.

### Smart notifications (`app/notifications/`, `notifications` table)

`NotificationService` is the only writer of the `notifications` table
(migration `0007`) — IN_APP notifications are fully implemented; `PUSH`
is architecture-ready (the `channel` concept exists) but not implemented
(no device-token storage, no APNs/FCM — out of scope for this phase).
Every notification-generating call site (`app/alerts/service.py`,
`app/sos/service.py`, `app/api/trips.py`, `app/services/group_service.py`)
goes through `notify()`/`notify_group_safely()`, never constructs a
`Notification` row directly, and never lets a notification failure break
the operation that triggered it.

Sources: a per-user alert (its own recipient) or a group-level alert
(every active group member) on creation; an SOS trigger (every active
group member, including the trigger user — a confirmation their SOS was
recorded); trip started/completed (every active group member); a member
joining or leaving (every *other* active group member).

**Deduplication**: a partial unique index on `(user_id, dedup_key) WHERE
dedup_key IS NOT NULL` — the real guarantee, not just an app-level check.
Alert/SOS dedup keys tie to the specific alert/SOS row id, so a still-
ongoing condition (the same alert row refreshed on each evaluation tick)
never spawns a second notification; only a genuinely new row does.
Join/leave/trip-lifecycle notifications skip `dedup_key` entirely —
they're infrequent, human-initiated events, not an automated signal that
could rapidly re-fire the way an alert can.

| Endpoint | Notes |
|---|---|
| `GET /notifications` | own notifications only, paginated, `?unread_only=true` supported |
| `GET /notifications/unread-count` | |
| `PATCH /notifications/{notification_id}/read` | same 404 whether missing or someone else's |
| `PATCH /notifications/read-all` | returns how many were actually marked |

The user id driving every one of these always comes from the verified
JWT — there is no `user_id` query/body parameter anywhere in this router.

### Weather integration (`app/weather/`)

Entirely optional and never load-bearing: `WeatherService.get_weather()`
never raises, and every call site (only `app/analytics/dashboard.py`)
treats `weather_available=False` as a completely normal outcome, not a
degraded state. `WEATHER_PROVIDER` is `"open-meteo"` (default — free, no
key required) or `"openweathermap"` (needs `WEATHER_API_KEY`; missing key
means `weather_available=False` immediately, no network call attempted).
Responses are cached in Redis, keyed by a coordinate rounded to ~1km
resolution, TTL'd at `WEATHER_CACHE_TTL_SECONDS` — Postgres never stores
weather; there is no weather-history table, only "the weather at the
group's current location right now." Warnings (`HEAVY_RAIN`, `HIGH_WIND`,
`LOW_VISIBILITY`) are deterministic threshold checks, transparently
documented in `app/weather/service.py` — never an automatic "unsafe to
travel" declaration.

### Demo mode (`app/demo/`)

`DEMO_MODE=true` registers an entirely separate router
(`app/api/demo.py`) with no per-request authentication of its own — every
route operates exclusively on one fixed, uuid5-derived demo group/trip
(`app/demo/data.py`'s `DEMO_GROUP_ID`/`DEMO_USER_IDS`) and accepts no
group/trip/user id from the caller at all, so there is no arbitrary id a
request could substitute to reach real data. **Never enabled
automatically**: `DEMO_MODE=true` together with `ENVIRONMENT=production`
is refused at startup with the same fail-fast `ValueError` pattern as a
missing production secret (see `app/core/config.py`). When `DEMO_MODE` is
left at its default `false`, every one of these routes is completely
absent from the app — a request to any of them is a genuine 404 (no
route matches), not a 403.

4 fixed demo members (fictional names, not modeled on any real person), 1
fixed demo group, and a ~5.5km demo route. `app/demo/simulator.py` drives
5 **deterministic** scenarios — the same scenario name always produces
the exact same tick-by-tick GPS sequence — feeding every point through
the real ingestion pipeline (`location_service.record_location`, live
state, presence), never fabricating analytics/alerts directly; the
already-running intelligence worker reacts to demo GPS exactly as it
would to genuine live tracking.

| Scenario | What it does |
|---|---|
| `normal` | all 4 members move together steadily to the route's end |
| `falling_behind` | 3 members move normally; 1 lags at reduced speed |
| `route_deviation` | 1 member drifts off the route for a window of ticks, then returns |
| `sos` | normal movement, with a real SOS triggered partway through |
| `completion` | reaches 100% and explicitly ends the trip (generating its analytics snapshot) |

| Endpoint | Notes |
|---|---|
| `POST /demo/reset` | ends any running demo trip; group/members persist as the reusable fixture |
| `POST /demo/scenarios/{scenario}/start` | starts a fresh demo trip+route and begins ticking |
| `POST /demo/scenarios/{scenario}/stop` | cancels the running scenario |
| `GET /demo/status` | current scenario, trip id, tick progress |

### Dashboard upgrade

`GET /trips/{trip_id}/dashboard` now also composes `risk` (DB-only, works
for any trip status), `eta` (individual + group, live-trip only), `weather`
(live-trip only, the representative member's current location), and
`notifications` (the *viewer's* own unread count — the endpoint now takes
the caller's verified user id specifically for this, never another
member's). A COMPLETED/CANCELLED trip's dashboard reports
`eta.eta_available=false` and `weather.weather_available=false` — both
are live-only concepts with nothing to report once a trip is over — while
`risk` and `notifications` still compute normally, since neither needs
Redis or a current location.

## Environment variables

Copy `.env.example` to `.env` and fill in real values — never commit `.env`.

- `SUPABASE_URL`, `SUPABASE_ANON_KEY` — from Settings > API in the Supabase dashboard
- `SUPABASE_SERVICE_ROLE_KEY` — same page. **Backend-only.** Never sent to the
  frontend, never returned in any API response, never logged.
- `DATABASE_URL` — Supabase Postgres connection string. Paste it exactly as
  Supabase gives it to you (`postgresql://...`) — the engine automatically
  rewrites that to `postgresql+psycopg://` internally, since this project
  installs `psycopg` (v3), not the legacy `psycopg2`.
- `JWT_SECRET` — Settings > API > JWT Settings > JWT Secret. This is what
  FastAPI uses to verify tokens Supabase issued.
- `FRONTEND_URL` — comma-separated allowed CORS origins, e.g. `http://localhost:3000`
- `REDIS_URL` — e.g. `redis://localhost:6379/0`. Powers live tracking only
  (WebSockets) — every REST endpoint and historical data work fine
  without it. Never sent to the frontend.
- `LIVE_LOCATION_TTL_SECONDS` (default `60`) — how long a live location
  stays valid before expiring out of Redis on its own.
- `PRESENCE_TTL_SECONDS` (default `60`) — how long a user stays ONLINE
  after their last heartbeat/location update before going stale.
- `MAX_LOCATION_UPDATES_PER_SECOND` (default `5`) — per-connection rate
  limit on the WebSocket.
- `WS_MAX_MESSAGE_BYTES` (default `8192`) — max WebSocket text frame size.
- Intelligence thresholds (all in `app/intelligence/thresholds.py`) —
  `STOP_SPEED_MPS` (`0.8`), `STOP_DURATION_SECONDS` (`120`),
  `STALE_LOCATION_SECONDS` (`60`), `FALLING_BEHIND_DISTANCE_METERS` (`500`),
  `FALLING_BEHIND_DURATION_SECONDS` (`120`),
  `GROUP_SEPARATION_DISTANCE_METERS` (`800`),
  `GROUP_SEPARATION_DURATION_SECONDS` (`120`),
  `ISOLATED_MEMBER_DISTANCE_METERS` (`1000`),
  `ISOLATED_MEMBER_DURATION_SECONDS` (`120`),
  `MAX_REASONABLE_SPEED_MPS` (`45`), `SPEED_ANOMALY_DURATION_SECONDS` (`20`),
  `GROUP_COHESION_DISTANCE_METERS` (`300`),
  `MIN_USABLE_ACCURACY_METERS` (`100`),
  `INTELLIGENCE_EVALUATION_INTERVAL_SECONDS` (`3`).
- Route intelligence thresholds (all in `app/intelligence/thresholds.py`,
  see the Route intelligence section above) —
  `ROUTE_ENDPOINT_TOLERANCE_METERS` (`200`) — how far a declared
  origin/destination may sit from the geometry's own first/last
  coordinate before route creation is rejected,
  `OFF_ROUTE_THRESHOLD_METERS` (`100`),
  `ROUTE_DEVIATION_DURATION_SECONDS` (`60`),
  `ARRIVAL_THRESHOLD_METERS` (`50`), `ARRIVAL_DURATION_SECONDS` (`30`),
  `ROUTE_PROGRESS_STALE_SECONDS` (`60`) — how old a live location can be
  and still be used for route matching, and `BASELINE_ROUTE_SPEED_MPS`
  (`11`, ≈40 km/h) — the ETA fallback when a route has no
  `estimated_duration_seconds`.
- Analytics (`app/analytics/`, see that section above) —
  `MAX_ANALYTICS_SPEED_MPS` (`45`) — a GPS-to-GPS segment implying a
  faster speed than this is treated as an impossible jump and excluded
  from distance-traveled calculations (accuracy filtering reuses
  `MIN_USABLE_ACCURACY_METERS` above rather than a second constant), and
  `ANALYTICS_CACHE_TTL_SECONDS` (`300`) — reserved for a future Redis
  read-through cache of completed-trip analytics (`trip_analytics_cache_key`
  in `app/core/redis_keys.py`); not yet wired to any endpoint, since the
  `trip_analytics_snapshots` table already serves that same purpose today.
- Production hardening (Phase 11, see that section above) —
  `ENVIRONMENT` (`development`/`test`/`production`), `LOG_LEVEL` (`INFO`),
  `ENABLE_DOCS` (`true`), `CORS_ALLOWED_ORIGINS` (preferred over
  `FRONTEND_URL`), `RATE_LIMIT_ENABLED` (`true`),
  `GENERAL_API_RATE_LIMIT_PER_MINUTE` (`100`),
  `AUTH_RATE_LIMIT_PER_MINUTE` (`10`),
  `JOIN_GROUP_RATE_LIMIT_PER_MINUTE` (`10`),
  `SOS_RATE_LIMIT_PER_MINUTE` (`5`),
  `WEBSOCKET_MESSAGES_PER_SECOND` (`10`),
  `WEBSOCKET_FLOOD_DISCONNECT_THRESHOLD` (`20`),
  `MAX_WS_CONNECTIONS_PER_USER` (`5`), `MAX_REQUEST_BODY_BYTES`
  (`1000000`), `DATABASE_POOL_SIZE` (`5`), `DATABASE_MAX_OVERFLOW` (`10`),
  `DATABASE_POOL_TIMEOUT_SECONDS` (`30`),
  `DATABASE_POOL_RECYCLE_SECONDS` (`1800`),
  `REDIS_CONNECT_TIMEOUT_SECONDS` (`5`), `REDIS_SOCKET_TIMEOUT_SECONDS`
  (`5`), `REDIS_RETRY_LIMIT` (`5`), `REDIS_RETRY_MAX_BACKOFF_SECONDS`
  (`30`), `LOCATION_RETENTION_DAYS` (unset — documented, not activated).
- Advanced features (Phase 12, see that section above) —
  `REPLAY_MIN_INTERVAL_SECONDS` (`2`), `REPLAY_MAX_INTERVAL_SECONDS`
  (`300`), `REPLAY_DEFAULT_INTERVAL_SECONDS` (`10`), `REPLAY_MAX_FRAMES`
  (`2000`); `RISK_LOW_MAX` (`30`), `RISK_MEDIUM_MAX` (`60`),
  `RISK_HIGH_MAX` (`80`), and one `RISK_WEIGHT_*` setting per factor
  (`ACTIVE_SOS` 50, `CRITICAL_ALERT` 30, `GROUP_SEPARATION` 17,
  `ISOLATED_MEMBER` 12, `FALLING_BEHIND` 10, `ROUTE_DEVIATION` 8,
  `UNEXPECTED_STOP` 8, `SPEED_ANOMALY` 8, `LOW_ACTIVE_RATIO` 10) plus
  `RISK_LOW_ACTIVE_RATIO_THRESHOLD` (`0.5`); `WEATHER_PROVIDER`
  (`open-meteo`), `WEATHER_API_KEY` (unset — only needed for
  `openweathermap`), `WEATHER_CACHE_TTL_SECONDS` (`900`),
  `WEATHER_REQUEST_TIMEOUT_SECONDS` (`5`); `DEMO_MODE` (`false` —
  **never** set `true` in production, refused at startup if you do) and
  `DEMO_TICK_INTERVAL_SECONDS` (`2`).
- `OSRM_URL` — reserved for a later phase, unused so far

## Local development

```bash
cd backend
python -m venv venv
./venv/Scripts/activate        # Windows; source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env           # then fill in real Supabase values
alembic upgrade head           # requires a real DATABASE_URL
uvicorn app.main:app --reload
```

Redis, locally: `docker run -p 6379:6379 redis:7-alpine`, then set
`REDIS_URL=redis://localhost:6379/0` in `.env`. Not required for the REST
API or its tests — only for exercising `WS /api/v1/ws/trips/{trip_id}`
against a real Redis instance instead of the test suite's fakeredis.

Run tests (these use a locally-signed test JWT and fakeredis, not a real
Supabase project or Redis server — see `tests/conftest.py`):

```bash
pytest -v
```

### Running demo mode

Requires a real, reachable `DATABASE_URL` (demo mode writes real rows —
a fixed demo group/trip — through the real ingestion pipeline) and,
ideally, `REDIS_URL` (live GPS/presence still work without it, degraded,
same as any other trip). Set in `.env`:

```bash
ENVIRONMENT=development   # DEMO_MODE=true is refused if ENVIRONMENT=production
DEMO_MODE=true
```

Then, with the server running:

```bash
curl -X POST http://localhost:8000/api/v1/demo/reset
curl -X POST http://localhost:8000/api/v1/demo/scenarios/normal/start
curl http://localhost:8000/api/v1/demo/status
curl -X POST http://localhost:8000/api/v1/demo/scenarios/normal/stop
```

Watch it live the same way any real trip's WebSocket/dashboard would be
watched — `WS /api/v1/ws/trips/{trip_id}` (the trip id comes back from
`/demo/status` or the `/start` response) and
`GET /api/v1/trips/{trip_id}/dashboard`.
