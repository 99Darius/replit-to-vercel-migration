# Vercel Express+Vite Pattern (Phase 1, step 3)

Replit's fullstack template = one Express server that both serves the Vite build AND the API, with extension-less ESM imports. Vercel's `@vercel/node` TS pipeline (nodenext) CANNOT compile those imports. Solution: pre-bundle the server with the project's own esbuild and point a thin Vercel function at the bundle.

## Standard API app (API + static SPA)

`server/serverless.ts` — exports the Express app, no `.listen()`:
```ts
import express from "express";
import { registerRoutes } from "./routes";
const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: false }));
const ready = registerRoutes(app);          // attaches /api/* handlers
app.use(async (_req, _res, next) => { await ready; next(); });
export default app;
```

`api/index.mjs`:
```js
export { default } from "../dist/serverless.js";
```

`vercel.json`:
```json
{
  "buildCommand": "vite build && esbuild server/serverless.ts --platform=node --packages=external --bundle --format=esm --outdir=dist",
  "outputDirectory": "dist/public",
  "rewrites": [{ "source": "/api/:path*", "destination": "/api" }]
}
```

**Why this works (despite review false-positives):**
- The rewrite `/api/:path*` → `/api` selects the function but Vercel passes the **original URL** to it, so Express's `app.use("/api", router)` still matches. (Reviewers will claim this 404s — it does not; curl proves it.)
- `--packages=external` keeps deps in node_modules; Vercel installs `dependencies` and NFT traces `api/index.mjs → ../dist/serverless.js → node_modules`. The build-output `dist/serverless.js` IS traced even though it's outside `api/`.
- Static assets are served by Vercel CDN from `outputDirectory` = `dist/public`.

## SSR app (server-renders some routes, e.g. for bots)

When Express itself must handle `/` and other non-API paths (SSR + SPA fallback), route EVERYTHING to the function and serve static from inside it:
```ts
// in serverless.ts, after registerRoutes resolves:
const publicDir = path.resolve(process.cwd(), "dist", "public");
app.use(express.static(publicDir));
app.use("*", (_req, res) => res.sendFile(path.resolve(publicDir, "index.html")));
```
```json
{
  "buildCommand": "vite build && esbuild ... && mkdir -p public_marker && echo ok > public_marker/.keep",
  "outputDirectory": "public_marker",
  "functions": { "api/index.mjs": { "includeFiles": "dist/public/**" } },
  "rewrites": [{ "source": "/(.*)", "destination": "/api" }]
}
```
- `includeFiles` bundles the static build into the lambda; `process.cwd()/dist/public` resolves to it at runtime (verified live).
- `outputDirectory` must be NON-EMPTY or Vercel errors ("Output Directory is empty") — hence the marker dir.

## Pure static site (no API)

```json
{ "buildCommand": "vite build", "outputDirectory": "dist/public" }
```
No `api/`, no `serverless.ts`. Confirm `registerRoutes` is genuinely empty and storage is unused.

## Deploy gotchas

- New projects: Deployment Protection ON → 401. Disable: `PATCH /v9/projects/<name> {"ssoProtection": null}`.
- `git push` only auto-deploys if the project is git-connected. Otherwise `vercel deploy --prod`. Always verify deploy age after a fix.
- Env var changes require a redeploy to take effect.
- Stateful needs (websockets, in-process schedulers, long-running jobs): serverless won't hold state. Move schedulers to Vercel Cron endpoints (CRON_SECRET-gated; Hobby = daily only), sessions to a PG store (`connect-pg-simple`), or use Fly.io for a persistent server.
