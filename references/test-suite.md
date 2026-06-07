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

## Run + debug loop

```bash
npx playwright test --workers=4
```
- On failure, use `superpowers:systematic-debugging` to find the ROOT cause (don't patch the test to pass). Real bugs that surface: missing `<title>`; a fix that didn't deploy (project not git-connected — check deploy age or `vercel deploy --prod`); a `secure` cookie with no `trust proxy`.
- Run ≥3× to confirm no flakiness before declaring green.
- 100% green is the gate for Phase 3 (cutover).
