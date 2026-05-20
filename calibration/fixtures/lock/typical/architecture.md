# Architecture
FastAPI auth service. JWT-based authentication. All tokens signed with HS256.
Sessions stored in Redis. Primary auth middleware in `app/middleware/auth.py` — every
authenticated route passes through it. Token rotation enabled; refresh tokens stored hashed.

Commit message:
    fix(auth): upgrade JWT signing from HS256 to RS256 with rotating key pairs

    HS256 is a symmetric algorithm — the same secret signs and verifies tokens.
    If the secret leaks (e.g., via env var exposure in logs), an attacker can mint
    arbitrary valid tokens for any user. RS256 separates signing (private key, server-only)
    from verification (public key, distributable). Rotating key pairs means a compromised
    key has bounded blast radius. Residual risk: key rotation must be coordinated across
    all services that verify tokens — added KEY_ID claim to facilitate gradual rotation.
    Closes #security-312.

