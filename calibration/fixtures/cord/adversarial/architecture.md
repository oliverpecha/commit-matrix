# Architecture
Full-stack monorepo. Postgres schema managed via Alembic migrations.
Frontend, backend, and 2 external API consumers all read from the users table.
Column 'email' is referenced in 14 backend query files and 3 frontend display components.

