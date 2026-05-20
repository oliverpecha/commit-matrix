# Architecture
FastAPI backend serving a public REST API. Consumers: mobile app (50k DAU), third-party integrators (12 partners).
Auth: JWT bearer tokens. /api/v1/users, /api/v1/auth, /api/v1/webhooks.
Integrators rely on documented field names in UserResponse schema.
