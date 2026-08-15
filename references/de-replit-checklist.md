# De-Replit Checklist (Phase 1, step 2)

`scripts/dereplit.py <dir>` automates the common Express+Vite single-server template. After running it, manually verify each item — the script does NOT catch everything.

## The full checklist

| Item | Where | Action |
|---|---|---|
| `.replit`, `.replitignore` | root | delete (or leave inert) |
| `replit.md` | root | keep as docs reference |
| `.local/` (100s of MB agent cache) | root | never unpack/commit (`unzip -x "*/.local/*"`) |
| `@replit/vite-plugin-*` (runtime-error-modal, cartographer, dev-banner) | vite.config.ts | remove imports + the `REPL_ID`-gated plugin block |
| same plugins | package.json deps + pnpm-workspace catalog | remove |
| **`replit-dev-banner.js` `<script>`** | **client/index.html** | **remove — vite-plugin strip misses this; it loads a replit.com script in prod** |
| `pnpm-workspace.yaml` platform overrides | root | remove the linux-x64-only `"esbuild>@esbuild/darwin-*": "-"` block (breaks local installs) |
| `process.env.REPL_ID` / `REPLIT_*` checks | anywhere | remove dead branches |
| `gitsafe-backup` git remote | .git | `git remote remove gitsafe-backup` |
| hardcoded fallback secrets | `SESSION_SECRET ?? "..."`, `ADMIN_KEY \|\| "..."` | fail-fast (throw if unset) |
| `PORT`/`BASE_PATH` required + `host:"0.0.0.0"`/`reusePort` | vite/server | default them; Vercel sets PORT. `reusePort` is Linux-only — fine if standalone entry is dead, but confirm. |
| Replit-proxied integrations | see `integrations.md` | swap to real providers |
| missing `app.set("trust proxy", 1)` | session apps | add it — required for `secure` cookies behind Vercel TLS |
| **backend that is never called** | `server/`, `shared/`, drizzle, neon deps | very common — the agent scaffolds its fullstack template for static sites. Detect + delete per `static-spa-apps.md` |
| `"name": "rest-express"` | package.json | Replit's unrenamed default; rename to the real project |

## Latent bugs to expect

Replit template code often never typechecked clean. Run `npx tsc --noEmit` and fix real errors (e.g. `err.error` vs `err.data?.error` in toast handlers, MemStorage create-methods missing nullable-field defaults before the spread, missing `<title>` in index.html). esbuild bundles without typechecking, so the build can succeed while `tsc` fails — fix anyway, tests will catch the runtime ones.

**Typechecking will not catch CSS.** Two classes of styling bug ship clean
through `tsc` and `vite build`:

- **Tailwind brand colours defined as `@layer components` classes** — every
  slash-opacity variant (`bg-brand/95`, `text-ink/70`) compiles to nothing at
  all. Can render a fixed nav with no background: white links on a white page.
  Detection + fix in `static-spa-apps.md`.
- **Unusable contrast** on generated palettes — mid-tone brand colour on a dark
  hero, "muted" text on a dark ground. The agent picks tokens that look fine in
  a swatch and fail on the page.

Neither surfaces in a build log. Look at rendered pages, and when a colour
misbehaves, grep the **compiled** CSS for the rule rather than trusting the
source.

## Verify clean

```bash
grep -rn "replit\|REPL_ID\|@replit" --include="*.ts" --include="*.tsx" --include="*.json" --include="*.html" . | grep -v node_modules
```
Should return only descriptive comments, never live code or the dev-banner script.
