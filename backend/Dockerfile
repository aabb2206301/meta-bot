# =============================================================================
# Backend image — Python 3.11 slim, installs requirements, runs migrations,
# starts uvicorn.
#
# Built and run via the root-level docker-compose.yml. The compose file
# bind-mounts ./app for live-reload during dev; in production, remove the
# mount and bake the code into the image instead.
# =============================================================================

FROM python:3.11-slim

# System deps for psycopg2 (sync driver used by Alembic) and build tools
# for any wheels that need compiling.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so we get Docker layer caching on requirements
# changes (most common edit in dev).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app code. In dev, docker-compose overrides this
# with a bind mount for live-reload.
COPY . .

# Default: run migrations then start the server. Override `command` in
# docker-compose if you want to skip migrations on a particular run.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]