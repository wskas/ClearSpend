# ---------------------------------------------------------------------------
# Stage 1 -- build the SPA
# ---------------------------------------------------------------------------
# Vite 8 requires Node 20+.
FROM node:22-alpine AS build

WORKDIR /app

# npm ci (not npm install) so the build uses package-lock.json exactly and a
# transitive dependency cannot drift between builds.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Baked into the bundle at build time -- Vite inlines VITE_* variables, so
# this cannot be changed at runtime and a rebuild is required to point the
# SPA at a different API.
#
# The default is the single-origin path. That collapses the CSP connect-src
# to 'self' (see the apiOrigin logic in vite.config.js) and means the browser
# issues no cross-origin request, hence no CORS preflight at all.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2 -- serve it, and reverse-proxy the API
# ---------------------------------------------------------------------------
FROM caddy:2-alpine

# Only the build output crosses the stage boundary: no node_modules, no
# source, no toolchain in the shipped image.
COPY --from=build /app/dist /srv/spa

# The Caddyfile itself is bind-mounted by compose rather than copied, so
# proxy configuration can be adjusted and reloaded without a rebuild of the
# frontend bundle.
