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

The Next.js frontend is now fully integrated with the FastAPI backend and Supabase Auth. It handles real-time GPS tracking, group synchronization, and renders the dynamic map interface.

To run the frontend:

```bash
cd frontend
npm install
npm run dev        # Starts the frontend at http://localhost:3000
```

## Backend

The real implementation is powered by FastAPI, Supabase Postgres + PostGIS, and WebSockets.

Completed Phases:
- **Phase 1** — FastAPI, Supabase Postgres + PostGIS, SQLAlchemy, Alembic, config, health check
- **Phase 2** — Supabase Auth, JWT verification, `/auth/me`, profile sync
- **Phase 3** — Groups: create, join by code, members, leader/member roles, leave/remove/transfer leadership
- **Phase 4** — Trips: create/start/end/cancel, state machine, one active trip per group
- **Phase 5** — GPS ingestion: submit + query location history, PostGIS storage
- **Phase 6** — Map Integration, Real browser GPS tracking (`useLocation`), and FastAPI WebSockets (Real-time group broadcast)

Not yet built: alerts engine, SOS, route intelligence, risk scoring, offline sync. See `backend/README.md` for full endpoint documentation.

To run the backend on macOS/Linux:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Ensure you have copied your Supabase credentials
# cp .env.example .env

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload  # Starts the backend at http://localhost:8000
```

## Security notes

- `SUPABASE_SERVICE_ROLE_KEY` exists only in backend environment variables —
  never in frontend code, never returned in an API response.
- The backend never trusts a user id from a request body/query string —
  every identity comes from a verified Supabase JWT.
- Never commit `.env`.
