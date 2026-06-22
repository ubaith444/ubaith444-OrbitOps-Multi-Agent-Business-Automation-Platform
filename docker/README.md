# Docker

Container definitions are colocated with each application:

- `apps/api/Dockerfile`
- `apps/web/Dockerfile`
- Root `docker-compose.yml`
- `infra/nginx/nginx.conf`

This directory documents the boundary without duplicating Dockerfiles. See [docs/deployment.md](../docs/deployment.md).
