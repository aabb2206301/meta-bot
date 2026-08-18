# =============================================================================
# Frontend image — Node 20 alpine, runs Vite dev server on 0.0.0.0:5173.
#
# Built and run via the root-level docker-compose.yml. The compose file
# bind-mounts ./src for live-reload during dev.
#
# For production: switch the CMD to a static-build + nginx serve pipeline.
# Out of scope for Phase 11 — the plan is dev-first.
# =============================================================================

FROM node:20-alpine

WORKDIR /app

# Install deps first for layer caching.
COPY package.json package-lock.json* ./
RUN npm install

# Copy the rest of the app code. In dev, docker-compose overrides this
# with a bind mount for live-reload.
COPY . .

EXPOSE 5173

# --host 0.0.0.0 makes the dev server reachable from outside the container
# (otherwise it binds to 127.0.0.1 inside the container, unreachable from
# the host's localhost:5173 mapping).
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
