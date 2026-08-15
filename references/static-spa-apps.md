# Static & SPA Repls (Phase 1, alternate path)

A large share of repls built by Replit's agent are **static front-ends wearing a
fullstack costume**. The agent scaffolds its Express + Drizzle + Neon template
regardless of what was asked, so a brochure site ships with a server that has
zero routes and a database that was never queried.

Migrating these as fullstack apps is wasted work and leaves a serverless
function, a Postgres provisioning step, and ~40 dependencies you do not need.
Detect the class first, then take this path instead of
`vercel-express-pattern.md`.

## Fingerprints of a dead backend

Strong signals, in rough order of reliability:

| Signal | Check |
|---|---|
| `registerRoutes` is an empty stub | `server/routes.ts` creates an httpServer and attaches nothing but comments |
| Client never imports shared types | `grep -rn "@shared" client/` returns nothing |
| Client makes no API calls | no `fetch("/api`, no `apiRequest(`, no `useQuery` with a real key |
| Build only runs the client | `vercel.json` / build script is `vite build` alone |
| Template package name | `"name": "rest-express"` — Replit's unrenamed default |
| Storage layer unused | `server/storage.ts` exported but never imported outside itself |
| Schema unused | `shared/schema.ts` defines a `users` table nothing references |

## Verify before deleting

Deleting a live backend is unrecoverable in a way deleting dead code is not.
Run all of these and require them all to come back empty:

```bash
grep -rn "@shared" client/                                  # shared types
grep -rnE "fetch\(['\"]/api|apiRequest\(|axios\." client/   # API calls
grep -rn "from \"\./storage\"\|from './storage'" server/    # storage use
grep -rnE "\.(get|post|put|patch|delete)\(" server/routes.ts
```

If any hit is real, this is a fullstack app — stop and use
`vercel-express-pattern.md`.

## What to remove

```bash
git rm -r server shared drizzle.config.ts replit.md
git rm client/src/lib/queryClient.ts     # only if no queries exist
```

Then strip from `package.json`:

- **Server**: `express`, `express-session`, `connect-pg-simple`, `memorystore`,
  `passport`, `passport-local`, `ws`, `bufferutil`
- **Database**: `drizzle-orm`, `drizzle-zod`, `drizzle-kit`,
  `@neondatabase/serverless`
- **Types**: the matching `@types/*` entries
- **Build**: `tsx`, `esbuild` (only the client build remains)
- **Data layer**: `@tanstack/react-query` *only if* the app makes no requests
- Scripts: `dev`/`start`/`db:push` → `vite` / `vite preview`
- Rename `"rest-express"` to the real project name

Also narrow `tsconfig.json` — the template includes `server/**/*` and
`shared/**/*`, and `tsc` fails on the now-missing paths:

```json
{ "include": ["client/src/**/*"], "compilerOptions": { "paths": { "@/*": ["./client/src/*"] } } }
```

Expect ~150+ packages to disappear. Confirm with `npm run check && npm run build`
before committing.

## The SPA rewrite — the bug that bites everyone

A static build on Vercel serves files. `/pricing` is not a file, so it 404s.
Only `/` works, which means the site looks fine right up until someone clicks a
nav link, reloads a page, or opens a deep link.

**Every client-routed SPA needs a catch-all rewrite:**

```json
{
  "buildCommand": "vite build",
  "outputDirectory": "dist/public",
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }],
  "headers": [
    {
      "source": "/assets/(.*)",
      "headers": [{ "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }]
    }
  ]
}
```

The `headers` block is optional but free: Vite emits content-hashed asset
filenames, so they are safe to cache permanently.

**If the site has both an apex and a `www` domain**, add a canonical redirect —
otherwise every URL exists twice. `redirects` must come **before** `rewrites`,
or the catch-all swallows the request and the redirect never fires:

```json
{
  "buildCommand": "vite build",
  "outputDirectory": "dist/public",
  "redirects": [
    {
      "source": "/(.*)",
      "has": [{ "type": "host", "value": "www.example.com" }],
      "destination": "https://example.com/$1",
      "permanent": true
    }
  ],
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

Vercel evaluates redirects → filesystem → rewrites, so this ordering is what
makes both work together. `$1` preserves the path.

**Also disable Deployment Protection.** New Vercel projects default to SSO
protection ON and return 401 to everyone — the most likely failure mode for a
public brochure site, and it looks like a broken deploy rather than a setting:

```bash
curl -X PATCH "https://api.vercel.com/v9/projects/<project>" \
  -H "Authorization: Bearer $VERCEL_TOKEN" \
  -H "Content-Type: application/json" -d '{"ssoProtection": null}'
```

This is only needed for client-side routing (wouter, react-router). A
single-page site with anchor scrolling does not need it — but adding it is
harmless, and the moment anyone adds a second route it becomes required.

**Verify every route, not just the homepage.** Read the real route list out of
the router first — do not use a placeholder list:

```bash
grep -oE 'path="[^"]+"' client/src/App.tsx     # wouter / react-router
```

```bash
ROUTES=$(grep -oE 'path="[^"]+"' client/src/App.tsx | cut -d'"' -f2)
for p in $ROUTES; do
  printf "%-20s %s\n" "$p" "$(curl -s -o /dev/null -w '%{http_code}' "https://<host>$p")"
done
```

All must be 200. A 404 means the rewrite is missing or misordered.

**This check silently self-passes if you invent the route names.** Once the
catch-all rewrite is in place, *every* path returns 200 — including routes that
do not exist. Running the loop against a guessed list therefore prints all-200
and proves nothing at all. The assertion only has meaning when the list came
from the router.

Once the rewrite is confirmed working, the useful negative test is the opposite
one: confirm a deliberately bogus path renders **your** 404 view rather than
Vercel's, which tells you the SPA is handling the fallback.

### Consequence: unknown paths return 200

The catch-all means `/does-not-exist` also returns 200 with your SPA's 404 view
inside. That is a soft-404: correct for users, invisible to crawlers. Acceptable
for most migrations — flag it to the user if the site depends on SEO, since
fixing it properly needs prerendering or a framework with real 404 status
support.

## Latent bug: Tailwind brand colours that silently do nothing

Replit's agent commonly defines a project palette as CSS variables plus
hand-written classes in `@layer components`:

```css
:root { --deep-navy: hsl(218, 43%, 16%); }

@layer components {
  .bg-deep-navy { background-color: var(--deep-navy); }
  .text-deep-navy { color: var(--deep-navy); }
}
```

This works for `bg-deep-navy` and **fails silently for every opacity variant**.
`bg-deep-navy/95`, `bg-steel-blue/5`, `text-charcoal/70`, `border-brand/10` are
not utilities Tailwind knows about — they are not in the theme, so no rule is
generated at all. No error, no warning; the element just has no background.

The symptom is easy to misread as a design choice until it lands somewhere
load-bearing — e.g. a fixed nav styled `bg-deep-navy/95` renders with **no
background**, giving white links on a white page.

**Detect** — audit every opacity utility in the source against the built CSS.
Run `npm run build` first; this reads the compiled output, which is the only
artifact that proves whether a rule exists:

```bash
python3 - "$(ls dist/public/assets/*.css)" <<'EOF'
import re, sys, pathlib
css = pathlib.Path(sys.argv[1]).read_text()
used = set()
for f in pathlib.Path("client/src").rglob("*.tsx"):
    used |= set(re.findall(
        r'\b((?:bg|text|border|ring|fill|stroke|from|to|via)-[a-z][a-z0-9-]*/\d+)',
        f.read_text()))
missing = sorted(c for c in used if c.replace("/", "\\/") not in css)
print(f"used: {len(used)}   MISSING: {len(missing)}")
for m in missing:
    print("  ", m)
EOF
```

Anything listed as MISSING renders with no effect at all. Expect a handful of
false positives from unused shadcn components whose CSS variables were never
defined (`--sidebar-*`, `--chart-*`) — check whether anything imports them
before chasing those.

**Fix** — promote the colours to real theme colours. Store the variables as bare
HSL channels so Tailwind can inject an alpha:

```css
:root {
  --deep-navy: 218 43% 16%;    /* channels only — no hsl() wrapper */
}
```

```ts
// tailwind.config.ts
colors: {
  "deep-navy": "hsl(var(--deep-navy) / <alpha-value>)",
}
```

Then delete the `@layer components` classes — Tailwind now generates
`bg-deep-navy`, `text-deep-navy`, *and* every `/NN` variant.

**Confirm against the compiled CSS**, which is the only thing that proves it:

```bash
grep -o '\.bg-deep-navy\\/95{[^}]*}' dist/public/assets/*.css
# .bg-deep-navy\/95{background-color:hsl(var(--deep-navy) / .95)}
```

Note this changes the meaning of `var(--deep-navy)` — any remaining raw
`background-color: var(--deep-navy)` must become `hsl(var(--deep-navy))` or use
the utility.

**Convert every token, not just the brand palette.** The shadcn scaffold defines
`--primary`, `--secondary`, `--destructive`, `--accent`, `--muted`, `--border`
and friends the same broken way, and `button.tsx` styles its hover states as
`hover:bg-primary/90`, `hover:bg-destructive/90`, `hover:bg-secondary/80`. Leave
those tokens alone and **every button on the site loses its hover feedback** —
silently, with a clean `tsc` and a clean build. Treating the shadcn tokens as
"out of scope" is a mistake; they are the ones with opacity variants baked into
components you did not write.

Run the detector above **after** converting; it catches exactly this.

## Wire up auto-deploy

Replit-migrated projects are usually created by `vercel deploy` from the CLI,
which leaves them **not git-connected** — pushes to GitHub then deploy nothing,
and you debug a "fix that didn't work" that was never deployed.

```bash
vercel git connect https://github.com/<owner>/<repo>.git --yes
git push origin main
vercel ls <project>          # a new deployment should appear within ~30s
```

Confirm by deployment age, not by assumption.
