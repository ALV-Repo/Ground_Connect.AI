# DB-013 — Redis Session Store & Authorization-Decision Cache

## Scope
PostgreSQL control-plane implementation for AUTH-10 / IDN-04:
- configurable idle and absolute session TTL
- refresh-token family tracking and reuse detection
- authorization-decision cache TTL limited to 60 seconds
- immediate-invalidation mechanism through authorization-version changes

## Boundary
PostgreSQL does not implement Redis. The application/Redis layer is responsible for:
- Redis session keys and EXPIRE
- atomic Redis operations
- actual authorization-decision cache entries
- immediate eviction of affected keys
- event consumption

PostgreSQL stores durable security metadata and the invalidation control state.

## Security
Raw refresh tokens are never stored. Only token hashes are stored.
A stale refresh token causes the complete token family to be revoked.

## Authorization invalidation
Call:
`redis_session_authorization.bump_authorization_version(...)`

Supported changes:
`hierarchy`, `role`, `grant`, `delegation`

Redis cache keys should include the tenant and authorization version, or otherwise reject a cached decision whose version is stale.

## Important
No project-wide grants table was invented. The existing grant implementation must call the invalidation function when its actual grant state changes.

## Files
- redis_session_authorization.sql
- redis_session_authorization_tests.sql
- README.md

The SQL must run after the existing tenant and identity/session schemas.
The PostgreSQL tests require at least one tenant and one user.
Redis TTL/key-eviction behavior requires a separate integration test.
