# replit-to-vercel-migration

A [Claude Code](https://claude.com/claude-code) skill for migrating Replit projects off Replit onto a standard stack: **GitHub + Vercel + Neon/Supabase + Vercel Blob + Fly.io**.

Covers the whole lifecycle for one repl or a whole portfolio:

1. **Audit** — enumerate every repl, back them all up as zips, find real deploy URLs + custom domains, classify each app's infra needs, and get portfolio-wide provider decisions (one DB provider, shared LLM keys) before touching anything.
2. **Migrate** (per app) — de-Replit the code, swap Replit-proxied integrations (OpenAI/Gmail/GCS/Sheets) for real providers, extract secrets, back up + restore the Postgres data, deploy to Vercel.
3. **Review + test + debug** — code review every migration, write Playwright E2E against the live deploy, loop with systematic debugging until 100% green. This is the gate before any cutover.
4. **Cutover** — user-driven, per-domain DNS switch, only on a confirmed-live build (zero downtime).
5. **Archive + decommission** — push archive-only repls to GitHub, then unpublish Replit deployments last.

## Layout

- `SKILL.md` — the workflow (5 phases).
- `references/` — deep-dives: audit/enumerate, de-Replit checklist, the Vercel+Express+Vite pattern, integration swaps, secret extraction, data migration, the Playwright suite.
- `scripts/dereplit.py` — automates the common Express+Vite template de-Replit.

## Install

Drop this directory into `~/.claude/skills/` (or a plugin's `skills/`). Requires the [superpowers](https://github.com/obra/superpowers-marketplace) plugin for code review + systematic debugging, plus `gh`, `vercel`, and `libpq` (`pg_dump`/`psql`).

## License

MIT
