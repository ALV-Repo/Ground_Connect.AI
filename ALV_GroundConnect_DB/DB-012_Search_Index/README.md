# DB-012 — OpenSearch Index Scoping & Search

## Requirements

- SRC-01: users, teams, messages, tasks, issues, reports, documents, locations.
- SRC-02: authorization inside the search query, before ranking/counts/suggestions.
- SRC-03: tenant-partitioned/scoped search index.
- SRC-04: Indian-language transliteration variants.
- TEN-04: automated cross-tenant leakage tests on the search path, every build, release-blocking.

## Files

- `opensearch_index_scoping.sql` — PostgreSQL-side search registry and tenant controls.
- `opensearch_index_scoping_tests.sql` — PostgreSQL contract tests.

## Important boundary

PostgreSQL does not create the physical OpenSearch index.

The search service must:
1. Maintain the tenant-scoped OpenSearch index.
2. Index records from `search_index.search_index_feed`.
3. Put tenant and authorization constraints inside every OpenSearch query.
4. Ensure unauthorized records cannot influence ranking, counts, aggregations or suggestions.
5. Configure language/transliteration analyzers.
6. Run TEN-04 cross-tenant search leakage tests in CI on every build.

The PostgreSQL tests do not claim to test a live OpenSearch cluster.

## Existing source-table integration

The registry uses resource types rather than duplicating users/tasks/issues/etc.
Existing user names are encrypted in `identity_authentication_sessions.users.name_encrypted`;
the approved indexing service must construct searchable representations through
the authorized application/decryption path.

## Execution

Run the SQL only after tenant/RLS dependencies exist, then run the PostgreSQL tests.
The OpenSearch implementation and TEN-04 CI gate are separate application/search work.
