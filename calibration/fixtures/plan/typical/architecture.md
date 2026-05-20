# Architecture
FastAPI backend with 3 external consumer services (mobile app, dashboard, webhook processor).
Routes: /api/v1/users, /api/v1/sessions, /api/v1/events. JWT auth. Postgres + SQLAlchemy.
All three consumers call /api/v1/users endpoints daily.
