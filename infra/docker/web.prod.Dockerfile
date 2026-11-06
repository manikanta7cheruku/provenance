# Production image for the web app: the built files served by an unprivileged nginx.
#
# The first stage builds the app. The second holds only the built files and the server, runs as a
# non-root user on port 8080, and proxies /api/ to the API on the internal network. Security headers
# for the pages are set in nginx.conf (the API sets its own).
#
# Build:  docker build -f infra/docker/web.prod.Dockerfile -t provenance-web:<git sha> .

FROM node:22-alpine AS build
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build


FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/nginx-health"]
