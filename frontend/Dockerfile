# syntax=docker/dockerfile:1

# ---- Build the React app ----------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# ---- Serve it with nginx; /api is proxied to the backend --------------------
FROM nginx:1.27-alpine
# Rendered by the image's entrypoint with envsubst (only ${BACKEND_URL} is substituted).
ENV BACKEND_URL=http://backend:3000 \
    NGINX_ENVSUBST_FILTER=^BACKEND_URL$
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
