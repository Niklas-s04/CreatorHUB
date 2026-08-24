# Build stage
FROM node:22-alpine AS build
WORKDIR /app
ARG VITE_API_BASE=/api/v1
ENV VITE_API_BASE=${VITE_API_BASE}

COPY package.json package-lock.json* /app/
RUN npm ci

COPY . /app/
RUN npm run build

# Run stage
FROM nginxinc/nginx-unprivileged:1.29-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY --chown=101:0 --chmod=644 nginx.conf /etc/nginx/conf.d/default.conf

HEALTHCHECK --interval=20s --timeout=3s --start-period=15s --retries=5 \
	CMD wget -q -O - http://127.0.0.1/healthz >/dev/null 2>&1 || exit 1

EXPOSE 80
