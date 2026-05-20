# Architecture
Authentication service. Primary auth layer for all user sessions.
Password hashing: bcrypt (cost factor 12). Session tokens stored in Redis.
This is the foundational auth primitive — every authenticated request passes through here.
