# Playwright E2E Suite (Phase 2, step 2)

Test the LIVE `.vercel.app` deployments (custom domains are still on Replit until cutover). Goal: prove the production build actually works before risking a DNS cutover.

## Setup

```
replit-exodus/
  package.json         # @playwright/test
  playwright.config.ts # testDir ./tests, retries: 2, ignoreHTTPSErrors
  urls.json            # { appKey: "https://<name>.vercel.app", ... }
  tests/
    helpers.ts         # loads urls.json
    <app>.spec.ts
```
`npm i -D @playwright/test && npx playwright install chromium`.

## What to assert per app

- **Page render**: `goto` status < 400, non-empty `<title>` (catches template `index.html` with no title), HTML does NOT contain `replit-dev-banner`.
- **Static asset loads** (SSR/SPA apps): extract `/assets/*.js` from HTML, fetch it → 200 (verifies the includeFiles/static path).
- **DB-backed APIs return migrated data**: `GET /api/<list>` → 200, array length ≥ expected, sample row has expected fields. Assert on a known migrated value where possible (e.g. a character name, a listing address).
- **Validation/auth/upload routes are wired**: POST invalid body → expect 400/401/409/500 but **never 404** (404 = route not mounted / rewrite broken).
- **OAuth entrypoint**: `GET /api/auth/<provider>` with `maxRedirects:0` → 30x with `location` containing the provider domain.

## Fallback: verifying without a browser

Playwright may be unavailable, or browser automation may hang mid-run (a stuck
extension, a sandbox with no localhost access). Do not let that block the gate —
most of what matters is checkable over HTTP. Say which mode you used when
reporting.

```bash
# Route matrix — every client route must be 200, not just the homepage.
# Take the list FROM THE ROUTER, never from memory: with an SPA catch-all
# rewrite in place every path returns 200, so a guessed list self-passes.
ROUTES=$(grep -oE 'path="[^"]+"' client/src/App.tsx | cut -d'"' -f2)
for p in $ROUTES; do
  printf "%-20s %s\n" "$p" "$(curl -s -o /dev/null -w '%{http_code}' "https://<host>$p")"
done

# Served by the new host, and no Replit residue.
curl -sI https://<host> | grep -i '^server'      # expect: Vercel
curl -s  https://<host> | grep -c replit          # expect: 0
curl -s  https://<host> | grep -o '<title>[^<]*</title>'   # expect: non-empty

# API still mounted (404 here means the rewrite broke).
curl -s -o /dev/null -w '%{http_code}\n' https://<host>/api/<known-route>
```

For CSS/styling claims, assert against the **compiled** stylesheet — it is the
only artifact that proves a utility exists:

```bash
CSS=$(curl -s https://<host>/ | grep -o 'assets/index-[A-Za-z0-9]*\.css')
curl -s "https://<host>/$CSS" -o build.css
grep -o '\.bg-brand\\/95{[^}]*}' build.css
```

Two cautions learned the hard way: write scratch files somewhere you have
confirmed write access (a silently-empty file reads as "0 matches" and fakes a
failure), and check byte count before trusting a grep result.

What this fallback cannot cover: visual regressions, contrast failures, hover
and focus states, and client-side interaction. Those need either a browser or
the user's own eyes — which is exactly what the Phase 3 spot-check gate is for.

## Run + debug loop

```bash
npx playwright test --workers=4
```
- On failure, use `superpowers:systematic-debugging` to find the ROOT cause (don't patch the test to pass). Real bugs that surface: missing `<title>`; a fix that didn't deploy (project not git-connected — check deploy age or `vercel deploy --prod`); a `secure` cookie with no `trust proxy`.
- Run ≥3× to confirm no flakiness before declaring green.
- 100% green is the gate for Phase 3 (cutover).
