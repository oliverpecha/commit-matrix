# Architecture
Docker Compose stack: api, worker, postgres, redis, nginx reverse proxy.
Shared `.env` file consumed by api and worker. Nginx config routes all external traffic.
Two environments: staging and production (same compose structure, different .env values).

Commit message: "chore(config): replace hardcoded credentials with env var references"

