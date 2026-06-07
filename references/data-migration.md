# Data Migration (Phase 1, step 5)

Replit's Postgres is Neon under the hood and externally reachable. Dump from the old, restore to the new Vercel-Marketplace Neon.

## Tools

`brew install libpq` → `pg_dump`/`psql` at `/opt/homebrew/opt/libpq/bin` (add to PATH). Use **plain `psql`/`pg_dump`**, never via a shell-rewriting proxy (e.g. rtk) — it can mangle the COPY stream mid-restore.

## Dump

```bash
pg_dump "<replit DATABASE_URL>" --schema=public --no-owner --no-privileges -f app-prod.sql
```
- `--schema=public` skips Replit's `_system` schema junk.
- For huge disposable tables (analytics/metrics), add `--exclude-table-data=public.<table>` — keeps schema, drops rows. (Don't `--column-inserts` over remote Neon for 10k+ rows; it's far too slow. Use COPY format = the default.)

## Restore

```bash
# enable extensions FIRST if used
psql "$DATABASE_URL_UNPOOLED" -c "CREATE EXTENSION IF NOT EXISTS vector;"
# strip the CREATE SCHEMA line (Neon already has public)
sed '/^CREATE SCHEMA public;$/d' app-prod.sql > restore.sql
psql "$DATABASE_URL_UNPOOLED" -v ON_ERROR_STOP=1 -q -f restore.sql
```
Use the **unpooled** URL for DDL/bulk restore.

## Known data gotchas

- **Empty-string in jsonb columns**: Replit apps sometimes store `''` in a jsonb/json column. `''` is invalid JSON → COPY aborts atomically (one bad row kills the whole table load). Either null those fields, or `--exclude-table-data` that table if it's non-critical showcase data and note the gap.
- **`vector` type missing**: pgvector tables fail with `type "public.vector" does not exist` → run `CREATE EXTENSION vector` before restore.
- The dump may include a `_system.replit_database_migrations_v1` table — strip/skip it.

## Verify

```bash
psql "$DATABASE_URL_UNPOOLED" -t -c "select count(*) from <table>"
```
Then confirm through the LIVE app API (e.g. an admin/list endpoint returns the migrated rows) — proves both the data and the app's DB wiring.
