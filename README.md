# RALLY

A group mobility & safety platform: create a group, start a trip together,
track everyone on a shared live map, get warned automatically when
something's wrong, and reach help instantly with one tap.

## What is RALLY?

RALLY is a real-time group trip tracker. A leader creates a group and a
trip, members join with a code, everyone shares their live location on one
map for the duration of the trip, and the backend continuously watches the
group's movement — flagging falling-behind members, group separation, route
deviation, unexpected stops, and speed anomalies — while giving every
member a one-tap SOS.

## Problem

Groups traveling together (road trips, hikes, campus/event groups, family
outings) lose track of each other constantly: phones die, signal drops,
someone takes a wrong turn, someone falls behind on a trail. There's no
shared picture of where everyone actually is, no automatic warning when the
group is drifting apart, and no fast way to signal a real emergency beyond
a phone call that assumes good signal and someone free to answer it.

## Solution

RALLY gives a group one shared live map for the length of a trip, backed by
a real backend (not a peer-to-peer hack) that:

- ingests everyone's GPS continuously and broadcasts it over WebSockets,
- runs a threshold-based intelligence engine over that GPS to detect real
  group-safety conditions automatically,
- turns the ones that matter into alerts and (for a genuine emergency) an
  explicit SOS with real-time delivery to the whole group,
- matches live position against a planned route for progress/ETA/deviation,
- computes a deterministic, explainable safety risk score,
- and — once the trip ends — gives the group real analytics, a replay of
  the whole trip, and a plain-language summary.

## Key Features

- **Groups & trips** — create/join by code, leader/member roles, a trip
  state machine (`CREATED → ACTIVE → COMPLETED`/`CANCELLED`).
- **Live tracking** — GPS ingestion + a WebSocket per active trip, Redis
  Pub/Sub fanning updates out to every connected member in real time.
- **Intelligence engine** — FALLING_BEHIND, GROUP_SEPARATION,
  ISOLATED_MEMBER, UNEXPECTED_STOP, SPEED_ANOMALY, ROUTE_DEVIATION;
  threshold + persistence detectors, never ML, never random.
- **Alerts + SOS** — an alert engine turns a sustained intelligence
  detection into an ACTIVE → ACKNOWLEDGED → RESOLVED alert; SOS is a
  completely separate, explicitly user-triggered emergency flow.
- **Route intelligence** — plan a route, match live position onto it,
  progress/ETA/deviation, PostGIS geometry.
- **Risk score** — a deterministic 0–100 safety score with named,
  weighted, explainable factors.
- **Analytics + trip history + dashboard** — distance/duration/route
  completion/alerts/SOS, per-member breakdowns, a chronological timeline,
  and one aggregated dashboard endpoint the frontend actually polls.
- **Trip replay** — a compact, evenly-sampled playback of a completed
  trip with play/pause/restart/speed controls.
- **Notifications** — per-user, deduplicated, unread-count + mark-read.
- **Weather** — optional, never load-bearing; the trip works with none of
  it configured.
- **Demo mode** — five deterministic backend-driven scenarios for a
  reliable, repeatable demo without touching real user data.

## Architecture

```
User
 │
 ▼
RALLY Frontend (Next.js)
 │              │
 ▼              ▼
Supabase Auth   REST + WebSocket (FastAPI)
 │                        │
 └──────────►  FastAPI  ◄─┘
                  │
      ┌───────────┼────────────┐
      ▼           ▼            ▼
PostgreSQL/    Redis        Intelligence
PostGIS      (live state,   Engine (background
(source of    presence,     evaluator, reads
 truth)       pub/sub)      Redis, writes
      │                     intelligence_events)
      │                            │
      ▼                            ▼
  Analytics  ◄──────────────  Alerts / SOS
  (dashboard, risk, ETA,          │
   replay, insights)              ▼
                             WebSocket broadcast
                             back to every member
```

- **Frontend → Supabase Auth**: the browser signs in directly against
  Supabase; FastAPI never sees a password and never issues its own tokens.
- **Frontend → FastAPI (REST)**: every request carries the Supabase
  access token; FastAPI verifies it and derives the user's identity from
  it — never from anything the client sends in a body/query string.
- **Frontend → FastAPI (WebSocket)**: one connection per active trip,
  token as a query param (browsers can't set WS headers), live location/
  presence/alert/SOS/route/intelligence events pushed in real time.
- **FastAPI → PostgreSQL/PostGIS**: the permanent source of truth for
  everything except "where is everyone *right now*."
- **FastAPI → Redis**: disposable, TTL'd live state (current location,
  presence, Pub/Sub fan-out for cross-instance broadcast, rate-limit
  counters). If Redis is flushed, live tracking just resets — no
  historical data is ever at risk.
- **Intelligence Engine**: a background loop re-evaluating every ACTIVE
  trip on an interval, reading Redis + PostgreSQL, writing
  `intelligence_events`.
- **Alerts/SOS**: the alert engine consumes intelligence events (never
  produces them); SOS is a separate, explicit, user-triggered flow.
- **Analytics**: read-only aggregation over everything the earlier layers
  already recorded.

## Tech Stack

| Layer | Stack |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, Framer Motion, Leaflet/react-leaflet, `@supabase/supabase-js` |
| Backend | FastAPI, SQLAlchemy, Alembic, Pydantic Settings, `python-jose`/PyJWT |
| Database | Supabase Postgres + PostGIS |
| Auth | Supabase Auth (JWT, verified — never issued — by FastAPI) |
| Real-time | Native WebSockets (FastAPI) + Redis Pub/Sub |
| Cache / live state | Redis |
| Testing | pytest (backend, 750+ tests), `tsc`/`next build`/ESLint (frontend) |
| Deployment | Docker (backend), any Node host (frontend), Supabase (managed Postgres), managed Redis |

## Frontend

`frontend/` — Next.js 14 App Router + TypeScript (strict) + Tailwind.
Fully wired to the real backend (no mock data in the production app paths):

- `lib/api/` — one typed function per backend endpoint, plus the shared
  fetch client (`lib/api/client.ts`) that attaches the Supabase access
  token, retries once through a token refresh on 401, and maps every
  backend error code to a friendly message (`lib/api/errors.ts`).
- `lib/ws/` — a typed WebSocket client with bounded exponential-backoff
  reconnect, matching the backend's real message contract exactly.
- `lib/realtime/RallyGroupService.ts` — the adapter that merges the REST
  dashboard (aggregates/safety/risk/eta/weather) with the WebSocket (live
  positions) into the UI's group/member/alert model.
- `lib/auth/` — Supabase session restore, refresh, and route protection.
- `lib/geo/` — throttled, null-safe GPS sharing (`navigator.geolocation`).
- `lib/format.ts` — null-safe formatters; the backend's `null` (can't be
  calculated) is never rendered as a fake `0`.

## Backend

`backend/` — FastAPI, phased and documented in full in
[`backend/README.md`](backend/README.md) (auth flow, every endpoint,
WebSocket protocol, Redis key model, intelligence thresholds, rate limits,
error envelope, and every environment variable). Summary:

- Supabase Postgres/PostGIS is the only database; Supabase Auth is the
  only identity provider — FastAPI only ever *verifies* tokens.
- A trip state machine (`CREATED → ACTIVE → COMPLETED`, or `CREATED →
  CANCELLED`), enforced both in the application layer and with a partial
  unique index (`UNIQUE(group_id) WHERE status='ACTIVE'`).
- Redis-backed live tracking, a background intelligence evaluator, an
  alert engine, a separate SOS system, route matching, analytics, replay,
  risk scoring, notifications, and an optional weather integration.
- Production hardening: rate limiting (fails open), structured request-id
  logging, a standard error envelope, `/health` (liveness) + `/health/ready`
  (readiness), Prometheus-style `/metrics`, CORS with no wildcard, security
  headers, request body size limits, graceful shutdown.

## Database

Supabase Postgres + PostGIS, migrated with Alembic (`backend/alembic/`).
12 tables: `profiles`, `groups`, `group_members`, `trips`,
`location_history`, `intelligence_events`, `alerts`, `sos_events`,
`routes`, `trip_analytics_snapshots`, `notifications`, plus PostGIS's own
`spatial_ref_sys`. Every table that needs one has a real PostGIS
`GEOGRAPHY`/`GEOMETRY` column with a GIST spatial index
(`idx_trips_destination`, `idx_location_history_location`,
`idx_alerts_location`, `idx_sos_events_location`, `idx_routes_geometry`,
`idx_intelligence_events_location`), alongside the composite b-tree
indexes each hot query path actually needs (`(trip_id, created_at)`,
`(trip_id, recorded_at)`, `(user_id, read_at)`, etc. — see
`backend/alembic/versions/`). Partial unique indexes enforce three
concurrency-sensitive invariants at the database level, not just in
application code: one ACTIVE trip per group, one unresolved alert per
intelligence event, one active intelligence event per `(trip, type,
subject)`, and one deduplicated notification per `(user, dedup_key)`.
Foreign keys cascade or restrict deliberately — trip-scoped data (GPS,
alerts, SOS, routes, notifications) cascades on trip deletion; a group
can't be deleted while it still has trip history (`ON DELETE RESTRICT`).

## Real-Time System

`WS /api/v1/ws/trips/{trip_id}?token=<supabase_access_token>` — one
connection per active trip. The connection is accepted first, then
authenticated/authorized, so a rejected client gets a structured JSON
error frame explaining why before the socket closes. Every accepted GPS
update is written durably to `location_history` *and* broadcast within
milliseconds to every other connected member via Redis Pub/Sub — one
subscriber task per trip per process, not one Redis connection per
message. Presence (ONLINE/OFFLINE), heartbeats, per-connection rate
limiting, a per-user connection cap, and a flood-disconnect threshold are
all enforced server-side. Redis is strictly disposable: everything it
holds is either TTL'd live state or a Pub/Sub channel — if it's flushed
or restarted, live tracking just resets, and no historical data is ever
at risk, because none of it lives there.

## Intelligence Engine

`backend/app/intelligence/` — turns raw GPS into group-level detections:
FALLING_BEHIND, GROUP_SEPARATION, ISOLATED_MEMBER, UNEXPECTED_STOP,
SPEED_ANOMALY, and the positive MOVING_TOGETHER state. Every detector is a
plain threshold + persistence check (see `app/intelligence/thresholds.py`)
— never ML, never random — a condition must hold continuously for its
configured duration before it's ever recorded, so one noisy GPS point
can't create a false event. A background evaluator re-analyzes every
ACTIVE trip on a fixed interval; a per-trip Redis lock stops two worker
instances from double-evaluating the same trip.

## Safety System

**Alerts** (`backend/app/alerts/`): the alert engine consumes intelligence
events (it has no idea detectors exist independently of it) and maps each
WARNING-tier detection to an alert with a lifecycle of `ACTIVE →
ACKNOWLEDGED → RESOLVED`. A partial unique index guarantees exactly one
alert per intelligence event, updated in place, never duplicated across
evaluation ticks.

**SOS** (`backend/app/sos/`): explicitly user-triggered, entirely separate
from alerts/intelligence. PostgreSQL is written first and is the
permanent record. A WebSocket disconnect, stale GPS, or a user going
offline can **never** resolve or cancel an SOS — only an explicit
acknowledge/resolve/cancel call can. A duplicate trigger from the same
user on the same trip returns the existing SOS instead of creating a
second one.

## Route Intelligence

`backend/app/route/` — a route is real PostGIS `LINESTRING` geometry.
Every intelligence tick projects each member's live position onto it
(Shapely, in-process, not a PostGIS round trip per GPS point) to compute
`ON_ROUTE`/`OFF_ROUTE`/`NEAR_DESTINATION`/`ARRIVED` states, group progress
(the median member's route fraction — resistant to one outlier), and a
`ROUTE_DEVIATION` intelligence event when a member stays off-route past a
duration threshold. Distance is always server-calculated from the
geometry — never trusted from the client.

## Analytics

`backend/app/analytics/` — read-only aggregation over everything the
earlier phases already recorded: trip distance/duration, route
completion, alert/SOS/deviation counts, per-member breakdowns, a
chronological timeline, and a plain-language insights summary. The
governing rule: `0` means genuinely zero; `null` means it couldn't be
calculated (no GPS, no planned route) — the frontend renders that as
"N/A"/"Unavailable," never a fabricated `0`. `GET /trips/{trip_id}/dashboard`
is the one endpoint the frontend actually polls — it composes route
progress, risk, ETA, weather, safety counts, and the viewer's own unread
notification count in a single call.

## Risk Engine

`backend/app/risk/` — a deterministic, explainable 0–100 score
(`GET /trips/{trip_id}/risk`) from real, already-persisted signals only
(active SOS, active alerts, active WARNING-tier intelligence events) —
never fabricated, never random, same inputs always produce the same
score. Every point of score traces back to a named, weighted factor with
a plain-language description (active SOS, a critical alert, group
separation, an isolated member, falling behind, route deviation, an
unexpected stop, a speed anomaly, a low active-member ratio).

## ETA

`backend/app/route/eta.py` — uses a member's live GPS speed when it's
usable (not near-stopped, not a sensor glitch), otherwise the route's own
declared average speed, otherwise a configured baseline. `eta_available`
is explicit — `false` only when nothing usable is left to fall back to,
and `eta_seconds` is `null` in that case, never `0`. A separate group ETA
uses the median remaining distance and the median speed among currently
moving members, so one straggler or one outlier can't distort it.

## Trip Replay

`GET /trips/{trip_id}/replay?interval_seconds=N` — a compact, evenly
sampled timeline (never every raw GPS point) spanning the trip's actual
GPS range; each member's most recent point at-or-before each sample time
is carried forward. `REPLAY_MAX_FRAMES` is a hard ceiling — a very long
trip gets a coarser interval automatically rather than an unbounded
response. The frontend's replay player (`components/dashboard/
TripReplayPlayer.tsx`) adds Play/Pause/Restart/Timeline scrubbing and
0.5×/1×/2×/4× speed on top of these backend-sampled frames.

## Notifications

`backend/app/notifications/` — per-user, in-app notifications for alerts,
SOS, trip lifecycle events, and group membership changes. A partial
unique index on `(user_id, dedup_key)` guarantees a still-ongoing
condition never spawns a second notification. `GET /notifications`,
`/notifications/unread-count`, and the two mark-read endpoints are all
scoped to the verified caller — there is no `user_id` parameter anywhere
in this router, so one user can never read or mark another's notifications.

## Demo Mode

`backend/app/demo/` — only ever registered when `DEMO_MODE=true` (refused
at startup together with `ENVIRONMENT=production`). Operates exclusively
on one fixed demo group/trip; no group/trip/user id is ever accepted from
the caller, so there's no way to reach real user data through it. Five
deterministic scenarios (`normal`, `falling_behind`, `route_deviation`,
`sos`, `completion`) feed synthetic-but-realistic GPS through the exact
same ingestion pipeline real tracking uses — the intelligence engine,
alerts, risk score, and analytics all react to it exactly as they would
to a genuine trip. `POST /demo/reset` returns it to a clean state without
touching any real user's data.

## Installation

```bash
git clone <this repo>
cd "New Rally"
npm install                 # installs the frontend + workspace packages
```

Requires Node.js 18+, Python 3.12, and a Supabase project (Postgres +
Auth). Redis is optional for REST-only development but required for live
tracking (WebSockets).

## Environment Variables

Copy the two example files and fill in real values — **never commit either
`.env` file.**

```bash
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

**Backend** (`backend/.env` — see `backend/.env.example` for the complete,
commented list including every intelligence/route/risk/replay threshold):

| Variable | Required | Notes |
|---|---|---|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | production | Settings > API |
| `SUPABASE_SERVICE_ROLE_KEY` | production | backend-only, never sent to the frontend |
| `DATABASE_URL` | production | Supabase Postgres connection string |
| `REDIS_URL` | production | powers live tracking only; REST + historical data work without it |
| `JWT_SECRET` | production | Settings > API > JWT Settings |
| `CORS_ALLOWED_ORIGINS` | | comma-separated, no wildcard — this API sends credentials |
| `ENVIRONMENT` | | `development` \| `test` \| `production` |
| `DEMO_MODE` | | never `true` with `ENVIRONMENT=production` (refused at startup) |

**Frontend** (`frontend/.env.local` — see `frontend/.env.local.example`):

| Variable | Notes |
|---|---|
| `NEXT_PUBLIC_API_URL` | FastAPI base URL, no trailing slash |
| `NEXT_PUBLIC_WS_URL` | `ws://` in dev, `wss://` in any real deployment |
| `NEXT_PUBLIC_SUPABASE_URL` | the same Supabase project the backend points at |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | the anon/public key — safe for the browser by design |

No secret ever belongs in the frontend. `SUPABASE_SERVICE_ROLE_KEY` exists
only in `backend/.env` / the backend's deployment environment.

## Database Setup

```bash
cd backend
python -m venv venv
./venv/Scripts/activate        # Windows; source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env           # fill in real Supabase values
alembic upgrade head           # creates every table, index, and constraint
```

`alembic upgrade head` is idempotent and safe to re-run — it only applies
migrations the target database hasn't seen yet. To confirm the database is
current: `alembic current` should print the same revision as `alembic
heads`.

## Running Backend

```bash
cd backend
./venv/Scripts/activate
uvicorn app.main:app --reload --port 8000    # http://localhost:8000
```

Or from the repo root: `npm run dev:api`. The intelligence worker starts
automatically as part of the app's lifespan — there's no separate worker
process to launch. Verify with `curl http://localhost:8000/api/v1/health`
(liveness — always 200) and `curl http://localhost:8000/api/v1/health/ready`
(readiness — 503 if Postgres/Redis aren't actually reachable).

## Running Frontend

```bash
cd frontend
npm install
npm run dev              # http://localhost:3000
```

Or from the repo root: `npm run dev:web`.

## Running Redis

```bash
docker run -p 6379:6379 redis:7-alpine
```

Then set `REDIS_URL=redis://localhost:6379/0` in `backend/.env`. Not
required for the REST API, its tests, or historical data — only for
exercising the WebSocket live-tracking layer against a real Redis
instance (the test suite uses `fakeredis` instead).

## Running Tests

```bash
cd backend
./venv/Scripts/activate
pytest -v                # 750+ tests — fakeredis + a locally-signed
                          # test JWT, no real Supabase/Redis required
```

Or from the repo root: `npm run test:api`. Frontend correctness is
verified via `npx tsc --noEmit`, `npm run lint`, and `npm run build`
(all three must be clean) from `frontend/` — there's no separate
frontend unit-test runner in this project yet.

## Production Deployment

**Startup order** (services should retry their own dependencies rather
than crash-loop when one isn't ready yet):

```
Supabase/PostgreSQL
        ↓
      Redis
        ↓
 Backend (runs `alembic upgrade head`, then starts uvicorn —
          see backend/docker-entrypoint.sh)
        ↓
     Frontend
```

**Backend**: `backend/Dockerfile` builds a container that runs pending
migrations (when `DATABASE_URL` is set) before starting uvicorn — see
`backend/docker-entrypoint.sh`. Set `ENVIRONMENT=production`, which makes
`DATABASE_URL`/`REDIS_URL`/`SUPABASE_URL`/`SUPABASE_ANON_KEY`/
`SUPABASE_SERVICE_ROLE_KEY`/`JWT_SECRET` all mandatory (the process
refuses to start with any missing) and refuses `DEMO_MODE=true` outright.
Set `CORS_ALLOWED_ORIGINS` to the real frontend origin only — never `*`.
Point a load balancer / orchestrator's health check at
`GET /api/v1/health/ready`, not `/health` (liveness never reflects a
downstream outage; readiness does).

```bash
cd backend
docker build -t rally-backend .
docker run -p 8000:8000 --env-file .env rally-backend
```

**Frontend**: `npm run build` (from `frontend/`, or `npm run build:web`
from the repo root) produces a standard Next.js production build —
deploy it to any Node host (Vercel, a container, etc.) with the four
`NEXT_PUBLIC_*` variables above set to the real backend's URL.

## API Documentation

Interactive Swagger UI at `GET /docs` and ReDoc at `GET /redoc` (both
served from the running backend — e.g. `http://localhost:8000/docs`),
generated directly from the FastAPI route definitions, so they're always
in sync with the real API surface. Set `ENABLE_DOCS=false` in a
deployment that shouldn't advertise its API publicly (removes `/docs`,
`/redoc`, and the raw OpenAPI schema entirely, not just a link to them).
See [`backend/README.md`](backend/README.md) for the full endpoint
reference, the WebSocket message contract, and the standard error
envelope, in prose.

## Demo Instructions

1. In `backend/.env`: `ENVIRONMENT=development`, `DEMO_MODE=true`, and a
   real `DATABASE_URL` (demo mode writes real rows through the real
   ingestion pipeline — it needs somewhere real to write them).
2. Start the backend (`uvicorn app.main:app --reload`).
3. From the frontend, sign in and go to **Settings** — the **Demo Mode**
   panel only appears when the backend actually has demo mode enabled.
4. Pick a scenario and press start. The panel links straight to the live
   dashboard, which shows the demo trip exactly like a real one — real
   WebSocket updates, real intelligence events, real alerts, real risk
   score — because it *is* one, just fed synthetic GPS.
5. **Reset** returns the demo group/trip to a clean state without
   touching any real user's data.

Or drive it directly against the API:

```bash
curl -X POST http://localhost:8000/api/v1/demo/reset
curl -X POST http://localhost:8000/api/v1/demo/scenarios/normal/start
curl http://localhost:8000/api/v1/demo/status
curl -X POST http://localhost:8000/api/v1/demo/scenarios/normal/stop
```

If live GPS isn't available during a presentation, fall back to demo mode
— never to hardcoded frontend fake data. Every scenario still exercises
the real backend, real database, real WebSockets, and the real
intelligence engine.

## Security notes

- `SUPABASE_SERVICE_ROLE_KEY` exists only in the backend's environment —
  never in frontend code, never returned in any API response, never logged.
- The backend never trusts a user id from a request body/query string —
  every identity comes from a verified Supabase JWT.
- Never commit `.env` / `.env.local` (both are gitignored — commit only
  the `.env.example` files).
