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

**Rate limiting**: not implemented yet (that's Redis, Phase 6+). Mobile
clients are expected to post every few seconds during an active trip;
`record_location()` is a single call so a limiter can wrap it later
without restructuring anything.

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
- `REDIS_URL`, `OSRM_URL` — reserved for later phases, unused so far

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

Run tests (these use a locally-signed test JWT, not a real Supabase
project — see `tests/conftest.py`):

```bash
pytest -v
```
