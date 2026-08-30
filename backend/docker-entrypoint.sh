#!/bin/sh
# Runs before every container start (Phase 14 — reproducible deployment,
# see "Startup order" in the README): migrations first, then the app.
# Mirrors app/main.py's own philosophy of degrading rather than crashing
# when DATABASE_URL isn't set — that's only ever true in a misconfigured
# deployment, and the app itself already reports it clearly via
# GET /health, so this doesn't hide the problem, just doesn't crash the
# container over it before uvicorn even gets a chance to serve /health.
set -e

if [ -n "$DATABASE_URL" ]; then
  echo "[entrypoint] DATABASE_URL is set - running 'alembic upgrade head'..."
  alembic upgrade head
else
  echo "[entrypoint] DATABASE_URL is not set - skipping migrations. GET /health will report the database as not_configured."
fi

echo "[entrypoint] Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
