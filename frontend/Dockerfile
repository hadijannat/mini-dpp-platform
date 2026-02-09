# Multi-stage Dockerfile for frontend development and production

# =============================================================================
# Base Stage
# =============================================================================
FROM node:20-alpine AS base

# =============================================================================
# Development Stage
# =============================================================================
FROM base AS development

WORKDIR /app

# Copy package files (context is repo root)
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY frontend/ .

# Copy shared registry as sibling (mirrors repo layout for @shared alias)
COPY shared/ /shared/

# Expose development port
EXPOSE 5173

# Development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# =============================================================================
# Build Stage — mirrors repo layout: /repo/frontend + /repo/shared
# =============================================================================
FROM base AS build

# Accept build-time env vars for Vite (baked into the JS bundle)
ARG VITE_API_BASE_URL
ARG VITE_KEYCLOAK_URL
ARG VITE_KEYCLOAK_REALM
ARG VITE_KEYCLOAK_CLIENT_ID
ARG VITE_COMMIT_SHA

WORKDIR /repo/frontend

# Copy package files (context is repo root)
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY frontend/ .

# Copy shared registry as sibling so @shared alias resolves correctly:
# vite.config.ts: path.resolve(__dirname, '../shared') → /repo/shared
COPY shared/ /repo/shared/

# Build the application (VITE_ ARGs are automatically available as env vars)
RUN npm run build

# =============================================================================
# Production Stage
# =============================================================================
FROM nginx:alpine AS production

# Copy built files
COPY --from=build /repo/frontend/dist /usr/share/nginx/html

# Copy nginx configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Run as non-root user (nginx:alpine includes this user)
RUN chown -R nginx:nginx /usr/share/nginx/html \
    && chown -R nginx:nginx /var/cache/nginx \
    && chown -R nginx:nginx /var/log/nginx \
    && touch /var/run/nginx.pid \
    && chown nginx:nginx /var/run/nginx.pid

USER nginx

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO /dev/null http://127.0.0.1:8080/ || exit 1

# Expose port (non-privileged)
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
