# Multi-stage build: compile the static bundle with Node, then serve it with
# a real static file server. `npm run dev` (the previous CMD here) starts
# Vite's development server — Vite's own docs are explicit that it is not
# hardened for public exposure and should never be the thing the internet
# talks to. This produces an actual production artifact instead.
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json .
RUN npm ci

COPY . .

# Vite inlines import.meta.env.VITE_* values into the bundle at build time,
# not at container runtime — so this has to be a build arg, not an
# environment variable read by a running process.
ARG VITE_BACKEND_URL=http://localhost:8000
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
RUN npm run build

# nginxinc/nginx-unprivileged, not the plain nginx image — the plain image's
# master process still runs as root (only its worker processes drop
# privileges); this one never runs as root at all, and binds 8080 instead
# of 80 since low ports need root to bind.
FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
