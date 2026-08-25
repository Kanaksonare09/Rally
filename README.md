# RALLY

RALLY is a group mobility & safety platform: create a group, start a trip
together, and track everyone's location on a shared live map — with alerts
for falling behind, separation, route deviation, and a one-tap SOS.

This repo is a monorepo: a Next.js frontend (currently mock-data-driven)
and a FastAPI backend (real, backed by Supabase Postgres/PostGIS) that the
frontend will progressively be wired up to.

## Structure

```
frontend/          Next.js 14 (App Router) + TypeScript + Tailwind + Framer Motion
backend/           FastAPI + Supabase Postgres/PostGIS + SQLAlchemy + Alembic
packages/shared/   Design tokens, distance/speed formatting, Haversine helper
packages/types/    Shared TypeScript types (User, Group, Trip, Alert, SOS, ...)
```

`packages/types` currently models the platform's intended full shape
(risk scoring, recommendations, realtime events) — the backend implements
this incrementally phase by phase; see `backend/README.md` for what's
actually built versus still ahead.

## Frontend

Mock-data-driven for now (a `GroupService` abstraction backed by
localStorage + a simulated interval), built out ahead of the backend so
the full product surface — auth, create/join group, live dashboard,
members, alerts, active trip, trip summary/history, settings — could be
designed and iterated on independently.

```bash
npm install
npm run dev:web        # http://localhost:3000
```

## Backend

Real implementation, phased. Done so far:

- **Phase 1** — FastAPI, Supabase Postgres + PostGIS, SQLAlchemy, Alembic, config, health check
- **Phase 2** — Supabase Auth, JWT verification, `/auth/me`, profile sync
- **Phase 3** — Groups: create, join by code, members, leader/member roles, leave/remove/transfer leadership
- **Phase 4** — Trips: create/start/end/cancel, state machine, one active trip per group
- **Phase 5** — GPS ingestion: submit + query location history, PostGIS storage

Not yet built: Redis, WebSockets/live broadcasting, alerts engine, SOS,
route intelligence, risk scoring, offline sync. See `backend/README.md`
for full endpoint documentation, the auth flow, and environment variables.

```bash
cd backend
python -m venv venv
./venv/Scripts/activate        # Windows; source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env           # fill in real Supabase values
alembic upgrade head
uvicorn app.main:app --reload  # http://localhost:8000
```

Or, from the repo root: `npm run dev:api` / `npm run test:api`.

## Security notes

- `SUPABASE_SERVICE_ROLE_KEY` exists only in backend environment variables —
  never in frontend code, never returned in an API response.
- The backend never trusts a user id from a request body/query string —
  every identity comes from a verified Supabase JWT.
- Never commit `.env`.
