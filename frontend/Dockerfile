# =============================================================================
# Frontend image — Node 20 alpine, runs Vite dev server on 0.0.0.0:5173.
#
# Built and run via the root-level docker-compose.yml. The compose file
# bind-mounts ./src for live-reload during dev.
#
# For production: switch the CMD to a static-build + nginx serve pipeline.
# Out of scope for Phase 11 — the plan is dev-first.
# =============================================================================

# =============================================================================
# Production frontend image — multi-stage build.
#
# Stage 1 builds a static bundle with `vite build`. VITE_* build args are
# baked into the JS at build time (Vite env vars are compile-time, not
# runtime) — set them as build args / env vars on the Railway frontend
# service, pointing at the backend service's public URL.
#
# Stage 2 serves the static bundle with `serve`, listening on Railway's
# injected $PORT. This replaces the old dev-server-in-prod setup, which is
# also what was tripping Vite's allowedHosts check against Railway's edge
# proxy Host header.
#
# For local dev, keep using `docker-compose.yml` / `npm run dev` — this
# Dockerfile is prod-only.
# =============================================================================

FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

ARG VITE_API_URL
ARG VITE_WS_URL
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL

RUN npm run build

FROM node:20-alpine
WORKDIR /app
RUN npm install -g serve

COPY --from=build /app/dist ./dist

# Railway sets $PORT dynamically — shell form so it actually expands.
CMD serve -s dist -l ${PORT:-4173}
