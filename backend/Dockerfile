FROM python:3.12-slim

WORKDIR /app

# psycopg[binary] doesn't need libpq-dev, but geoalchemy2/postgis client
# tooling benefits from a minimal build toolchain being available.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

# Runs migrations (when DATABASE_URL is set) before starting uvicorn, so
# a fresh container is reproducible on its own — see docker-entrypoint.sh
# and the README's "Startup order" section.
ENTRYPOINT ["./docker-entrypoint.sh"]
