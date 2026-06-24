# Production Deployment Skeleton

This repository includes a Docker Compose skeleton for a production-like deployment. It wires the web frontend, FastAPI backend, a placeholder worker, PostgreSQL, RocketMQ, and MinIO without embedding real secrets.

## Files

- `docker-compose.yml`: service topology, volumes, health checks, and environment wiring.
- `docker/backend.Dockerfile`: Python runtime image for the FastAPI backend.
- `docker/frontend.Dockerfile`: Vite build stage plus Nginx static runtime.
- `docker/frontend.nginx.conf`: static SPA serving and `/api/` reverse proxy to the backend service.
- `.env.example`: copyable environment template with placeholder values only.

## First Deployment

1. Copy the environment template:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Replace every `replace-with-*` value in `.env` with deployment-specific secrets. Do not commit `.env`.

3. Review externally visible origins and ports:

   - `FRONTEND_HTTP_PORT` controls the host port exposed by Nginx.
   - `ALLOWED_ORIGINS` should contain the public HTTPS origin used by browsers.
   - Terminate TLS at a reverse proxy or load balancer in front of `frontend`.

4. Build and start the stack:

   ```powershell
   docker compose up -d --build
   ```

5. Check service health:

   ```powershell
   docker compose ps
   docker compose logs backend
   ```

6. Run database migrations when the migration set is ready for the target release:

   ```powershell
   docker compose run --rm backend alembic upgrade head
   ```

## Service Notes

- `frontend` serves the compiled React app with Nginx and proxies `/api/` to `backend`.
- `backend` runs `uvicorn app.main:app` on port `8000` inside the Compose network.
- `worker` runs `python -m app.worker` using the backend image. The worker entrypoint consumes the configured queue through the `QueueAdapter` boundary.
- `postgres` persists data in the `postgres-data` named volume.
- `rocketmq-namesrv` and `rocketmq-broker` provide the queue backbone expected by `QUEUE_PROVIDER=rocketmq`.
- `minio` stores object data in the `minio-data` named volume, and `minio-init` creates the configured bucket.

## Secret Handling

The committed `.env.example` contains placeholders only. Production secrets should come from a protected `.env`, a secrets manager, or platform-managed environment variables. At minimum rotate and protect:

- `POSTGRES_PASSWORD`
- `AUTH_TOKEN_SECRET`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `MINIO_ROOT_USER`
- `MINIO_ROOT_PASSWORD`
- `LLM_API_KEY` or `DEEPSEEK_API_KEY` when real model calls are enabled
- `KNOWLEDGE_API_KEY` when the knowledge-base API requires authentication

## Operational Gaps To Close Before Go-Live

- Add TLS termination, request limits, and access logs at the public ingress.
- Wire `RocketMQQueueAdapter` to the organization's approved RocketMQ Python client package before enabling production task execution.
- Confirm RocketMQ broker configuration for the target network, storage class, and retention policy.
- Decide whether MinIO is internal-only or exposed through a controlled object-storage endpoint.
- Add backup and restore procedures for PostgreSQL and MinIO volumes.
- Pin image tags to the organization's approved base-image policy during release hardening.
