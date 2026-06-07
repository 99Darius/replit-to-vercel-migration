# Audit & Enumerate (Phase 0)

No official Replit export CLI. Everything is browser-driven via a logged-in session (Playwright MCP, persistent profile).

## Enumerate all repls

```
navigate https://replit.com/repls
click "Load more" until gone
```
Extract per card:
```js
() => {
  const items = [...document.querySelectorAll('li')].filter(li => li.querySelector('a[href*="replId="]'));
  return items.map(li => {
    const a = li.querySelector('a[href*="replId="]');
    return {
      name: a.textContent.trim(),
      href: a.getAttribute('href'),         // /@user/Slug?replId=...
      status: li.querySelector('a[href*="deploymentPane"] img')?.getAttribute('aria-label')
        || (li.textContent.includes('Private') ? 'Private(no-deploy)' : 'none'),
    };
  });
}
```
Save to `inventory.json`. Note repls owned by collaborators (different `@owner` in href) — download from their namespace.

## Download zips (full backup)

Navigate the browser to `https://replit.com/@<user>/<Slug>.zip`. Playwright saves to `~/.playwright-mcp/<Slug>.zip`. Wait for the "Downloaded file" event — Replit packs the workspace on demand (15-30s+ for big ones). Batch ≤4 anchor-clicks with 5s gaps; Chrome drops beyond ~6 concurrent. Retry stragglers by direct navigation. Archive all zips somewhere durable (they ARE the backup).

## Find true deploy URLs + custom domains

`<slug>.replit.app` guessing fails ~50% (deploy subdomains differ, e.g. `belayar-estate-1-dariuscheung.replit.app`). For each repl, navigate `...?deploymentPane=true` and scrape app links:
```js
() => [...document.querySelectorAll('a[href]')].map(a => a.href)
  .filter(h => (h.includes('.replit.app') || (!h.includes('replit.com') && h.startsWith('http')))
    && !h.includes('replit.dev') && !h.includes('replit.com/refer'))
```
First `.replit.app` = real deploy URL; bare custom domains = the production domains. `dig +short <domain>` — Replit's anycast edge is `34.111.179.208`.

## Classify stack (no unpack)

```bash
unzip -p <zip> "<root>/package.json"   # deps → lang, PG, AI, storage, auth, email, ws
unzip -p <zip> "<root>/.replit"        # deploymentTarget, modules, ports
unzip -p <zip> "<root>/replit.md"      # human description of the app
```
Detect husks: `unzip -l <zip>` shows only `.local/` + `attached_assets/`, no source → archive attached_assets, skip migration.

## Decisions to extract (AskUserQuestion, portfolio-wide)

- DB provider (count PG DBs first: ≤~10 free Neon, else Supabase Pro / paid Neon).
- One shared LLM key per provider vs per-app.
- Keep-live vs archive-only list (let user check/uncheck each).
- Object storage (Vercel Blob), email (Resend), per-app custom domains, cutover timing.
