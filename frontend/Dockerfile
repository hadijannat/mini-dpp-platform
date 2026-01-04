# Multi-stage Dockerfile for frontend development and production

# =============================================================================
# Base Stage
# =============================================================================
FROM node:20-alpine as base

WORKDIR /app

# =============================================================================
# Development Stage
# =============================================================================
FROM base as development

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Expose development port
EXPOSE 5173

# Development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# =============================================================================
# Build Stage
# =============================================================================
FROM base as build

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# =============================================================================
# Production Stage
# =============================================================================
FROM nginx:alpine as production

# Copy built files
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
