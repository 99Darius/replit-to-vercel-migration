---
name: replit-to-vercel-migration
description: Use when migrating one or many Replit projects (repls) off Replit to a standard stack — GitHub + Vercel + Neon/Supabase + Vercel Blob/Fly. Covers portfolio audit, infra decisions, de-Replit code surgery, secret extraction, data migration, deploy, code review, Playwright tests, systematic debugging, and a user-gated DNS cutover + decommission. Triggers on "migrate my replit projects", "move off replit", "get my repls onto vercel".
---

# Replit → Vercel Migration

Migrate Replit projects to: **GitHub** (private repos) + **Vercel** (hosting) + **Neon or Supabase** (Postgres/vector) + **Vercel Blob** (object storage) + **Fly.io** (only for genuinely stateful/long-running servers).

**Announce at start:** "I'm using the replit-to-vercel-migration skill."

**Core principle:** Audit the whole portfolio and get infra decisions BEFORE migrating anything. Per app: de-Replit → deploy → **review → test → debug until green** → then, only on a confirmed-live build, the user provisions DNS and you cut over. Decommission Replit LAST.

## Prerequisites (install once)

1. **superpowers** — this skill leans on `superpowers:code-reviewer` and `superpowers:systematic-debugging`. If not installed: `claude plugin marketplace add obra/superpowers-marketplace && claude plugin install superpowers`.
2. **CLIs authed**: `gh auth status`, `vercel whoami`. Postgres tools: `brew install libpq` (gives `pg_dump`/`psql` at `/opt/homebrew/opt/libpq/bin`).
3. **Playwright MCP** for the browser-driven Replit export + DNS work, plus `@playwright/test` for the E2E suite.

## Phase 0 — Portfolio audit (do this ONCE, before any migration)

Holistic decisions are cheaper than per-app ones. See `references/audit-and-enumerate.md`.

1. **Enumerate** every repl: Playwright → log into replit.com once (persistent profile) → `https://replit.com/repls` → click "Load more" until exhausted → scrape `a[href*="replId="]` for name/slug/replId/deploy-status/age. Watch for repls owned by collaborators.
2. **Download all** as backup: navigate browser to `https://replit.com/@<user>/<Slug>.zip` (only works logged-in; curl gets 403). Batch ≤4 anchor-clicks with 5s gaps; poll `~/.playwright-mcp/*.zip`.
3. **Find real deploy URLs + custom domains**: scrape each repl's `?deploymentPane=true` (slug-guessing `<slug>.replit.app` is wrong half the time). Record custom domains; `dig` them (Replit's edge is `34.111.179.208`).
4. **Classify stack** without unpacking: `unzip -p <zip> "<root>/package.json"` + `.replit` + `replit.md`. Detect: lang, Postgres (drizzle/pg/@neondatabase), AI providers (openai/anthropic/...), object storage (@replit/object-storage, @google-cloud/storage), auth (passport/openid), email (nodemailer/sendgrid/resend), websockets, deployTarget. Flag **husks** (only `.local/` + attached_assets, no code) — archive, don't migrate.
5. **Present the matrix + get decisions** (use AskUserQuestion), made **across the whole portfolio**:
   - **DB provider**: ≤~10 PG DBs → free Neon via Vercel Marketplace (`vercel integration add neon`); ~20+ → one Supabase Pro or paid Neon org. Count first.
   - **Shared LLM keys**: if N apps need OpenAI, provision ONE key, reuse (store encrypted — see `references/secrets.md`).
   - **Which apps stay live** vs archive-only (code-to-GitHub, no deploy). Let the user check/uncheck each.
   - Object storage, email provider, per-app domains.

## Phase 1 — Per-app migration (repeat for each KEEP-LIVE app)

Full detail in `references/de-replit-checklist.md` and `references/vercel-express-pattern.md`.

1. **Unpack** clean: `unzip -q <zip> -x "*/.local/*"` (`.local/` is 100s of MB of agent cache).
2. **De-Replit the code** (run `scripts/dereplit.py <dir>` for the common Express+Vite template, then verify):
   - Strip `@replit/vite-plugin-*` imports + deps from vite.config + package.json.
   - **Remove `client/index.html`'s `replit-dev-banner.js` `<script>`** (the vite-plugin strip does NOT touch this — easy to miss; it ships a replit.com script to prod).
   - Remove `pnpm-workspace.yaml` platform overrides that pin native binaries to linux-x64 only (breaks local installs).
   - Replace Replit-proxied integrations with real ones (see `references/integrations.md`): OpenAI `AI_INTEGRATIONS_*` → `OPENAI_API_KEY`; Gmail connector → Resend; GCS sidecar → Vercel Blob; object storage → Vercel Blob; Google Sheets connector → service account.
   - Drop hardcoded fallback secrets (`SESSION_SECRET ?? "..."`, `ADMIN_KEY || "..."`) → fail-fast.
   - Add `app.set("trust proxy", 1)` for ANY app using `secure` session cookies (Vercel terminates TLS; without it the cookie is silently dropped → login broken).
3. **Add the Vercel entry** (`references/vercel-express-pattern.md`): `server/serverless.ts` exports the Express app (no `.listen()`); `api/index.mjs` re-exports the esbuild bundle; `vercel.json` builds vite + esbuild and rewrites `/api/:path*` → `/api`. Vercel preserves the original URL to the function, so Express's own `/api` mount matches. For SSR apps, route ALL paths to the function and serve static via `express.static` + `includeFiles`.
4. **Extract secrets** from the repl (`references/secrets.md`): DB URL from Database pane → Settings; app secrets via the Secrets pane's "Copy secret value" buttons + a `navigator.clipboard.writeText` override to capture (reveal-in-DOM doesn't work). Never print full secret values.
5. **Back up + migrate data** (`references/data-migration.md`): `pg_dump --schema=public --no-owner --no-privileges`; for junk/analytics tables add `--exclude-table-data`; strip `CREATE SCHEMA public;` before restore; restore with **plain `psql`** (not via any shell-rewriting proxy). Enable `CREATE EXTENSION vector` first if pgvector is used. Replit jsonb columns may hold empty strings (invalid JSON) — null them or exclude.
6. **GitHub + Vercel + DB**:
   - `gh repo create 99Darius/<name> --private --source . --remote origin --push`
   - `vercel link --yes --project <name>`; `vercel integration add neon` (provisions + connects + writes `.env.local` in one shot); restore the dump into the new Neon DB.
   - `vercel blob create-store <name> --access public`, then connect via API `POST /v1/storage/stores/<id>/connections {projectId, envVarEnvironments}` (auto-injects `BLOB_READ_WRITE_TOKEN`). There is no `blob store add` subcommand.
   - Set env: shared LLM keys, app secrets, fresh `SESSION_SECRET`.
   - `vercel deploy --prod`. **New projects default to Deployment Protection ON (401)** — disable via API `PATCH /v9/projects/<name> {"ssoProtection": null}` for public apps.
   - Attach custom domain to the Vercel project (`POST /v10/projects/<name>/domains`) — but DO NOT touch DNS yet.

## Phase 2 — Review, test, debug (gate before cutover)

**Do not cut over DNS until this phase is green.**

1. **Code review**: `superpowers:code-reviewer` per migrated repo. Focus: de-Replit completeness, serverless-entry correctness, `trust proxy`, secret handling, the integration swaps. **Verify findings against the live deploy** — reviewers reliably false-positive on the `/api` rewrite ("strips path → 404"), `dist/` tracing, and `process.cwd()` static paths; all three work on Vercel in practice, so curl the endpoints before "fixing".
2. **Write Playwright E2E** (`@playwright/test`) against the live `.vercel.app` URLs (custom domain is still on Replit until cutover). Per app assert: page renders + non-empty `<title>` + no `replit-dev-banner`; DB-backed APIs return the migrated rows; auth/upload/validation routes are wired (not 404). See `references/test-suite.md`.
3. **Loop with `superpowers:systematic-debugging`** until 100% green, run ≥3× for flakiness. Real bugs surface here (e.g. a template `index.html` with no `<title>`; fixes that didn't deploy because the project isn't git-connected — verify deploy age or `vercel deploy --prod` explicitly).

## Phase 3 — User-gated cutover (per domain, one at a time)

**The user must drive DNS. Each app must be confirmed live-and-working first.**

1. Confirm the `.vercel.app` build is green (tests pass, manual spot-check).
2. **User provisions DNS** at their registrar. For internet.bs: they log in (Playwright), you switch the apex `A` record `34.111.179.208` → Vercel (`76.76.21.21`) and any `www` CNAME → `cname.vercel-dns.com`. Lower TTL first if you want fast rollback.
3. Wait for propagation + Vercel SSL issuance; verify the custom domain serves the new build (not Replit). Keep Replit deployment up until verified — zero downtime.
4. Only then move to the next domain.

## Phase 4 — Archive + decommission (LAST)

1. **Archive-only repls**: push their code to private GitHub repos as reference (no deploy). Dump any DBs with real data first. Husks: keep the zip only.
2. **Decommission Replit** — ONLY after every kept domain is cut over and verified: unpublish each Replit deployment (stops compute billing). Keep the repls themselves for a grace period before deleting.

## Red flags

| Thought | Reality |
|---|---|
| "I'll just guess `<slug>.replit.app`" | Wrong half the time. Scrape `?deploymentPane=true`. |
| "The reviewer says the rewrite 404s — fix it" | Curl it first. Vercel preserves the URL; it works. |
| "git push will auto-deploy my fix" | Only if git-connected. Check deploy age / `vercel deploy --prod`. |
| "Secure cookie, I'm done" | Add `trust proxy` or login silently breaks on Vercel. |
| "DNS cutover now, then test" | Cut over LAST, per-domain, on a verified-live build. |
| "Decommission Replit, migration's done" | Only after every domain verified on Vercel. |
