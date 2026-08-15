#!/usr/bin/env python3
"""De-Replit a standard Replit fullstack template (Express+Vite single server).

FULLSTACK PATH ONLY. This writes server/serverless.ts + api/index.mjs and
overwrites vercel.json with the API-rewrite config. Do NOT run it on a repl
whose backend is dead code (empty registerRoutes, no client API calls) — you
would immediately undo its output, and it raises if server/ is already gone.
For that case see references/static-spa-apps.md.
"""
import json, re, sys, os

os.chdir(sys.argv[1])

if not os.path.isdir("server"):
    sys.exit("no server/ directory — this looks like the static path; "
             "see references/static-spa-apps.md instead of running this script")

# vite.config.ts: strip @replit plugins
if os.path.exists("vite.config.ts"):
    src = open("vite.config.ts").read()
    src = re.sub(r'import [a-zA-Z]+ from "@replit/[^"]+";\n', '', src)
    src = re.sub(r'    [a-zA-Z]+\(\),\n    \.\.\.\(process\.env\.NODE_ENV[\s\S]*?: \[\]\),\n', '', src)
    src = re.sub(r'\s*runtimeErrorOverlay\(\),', '', src)
    open("vite.config.ts","w").write(src)

# package.json: drop @replit deps
d = json.load(open("package.json"))
for sec in ("dependencies","devDependencies"):
    d[sec] = {k:v for k,v in d.get(sec,{}).items() if not k.startswith("@replit/")}
open("package.json","w").write(json.dumps(d, indent=2)+"\n")

# client/index.html: strip the Replit dev-banner <script> (the vite-plugin
# strip above does NOT touch this — it ships a replit.com script to prod).
for html in ("client/index.html", "index.html"):
    if os.path.exists(html):
        lines = open(html).read().splitlines(keepends=True)
        kept = [l for l in lines
                if "replit-dev-banner" not in l
                and "replit script which adds a banner" not in l]
        open(html, "w").write("".join(kept))

# serverless entry
os.makedirs("api", exist_ok=True)
open("server/serverless.ts","w").write('''// Vercel serverless entry: Express app with API routes only (static assets
// are served by Vercel from the vite build output).
import express from "express";
import { registerRoutes } from "./routes";

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: false }));

// registerRoutes attaches all /api handlers asynchronously; gate requests
// until registration completes.
const ready = registerRoutes(app);
app.use(async (_req, _res, next) => {
  await ready;
  next();
});

export default app;
''')
open("api/index.mjs","w").write('''// Vercel function entry. The Express app is pre-bundled by buildCommand
// (esbuild) because Vercel's TS pipeline can't compile the template's
// extension-less ESM imports.
export { default } from "../dist/serverless.js";
''')
open("vercel.json","w").write(json.dumps({
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "buildCommand": "vite build && esbuild server/serverless.ts --platform=node --packages=external --bundle --format=esm --outdir=dist",
  "outputDirectory": "dist/public",
  "rewrites": [{"source": "/api/:path*", "destination": "/api"}]
}, indent=2)+"\n")

if os.path.exists(".replit"): os.remove(".replit")

# Check each entry independently. Gating the whole block on ".vercel not in gi"
# meant a repo that already ignored .vercel never got .env / .env.* / .local/
# added — a secret-leak path.
gi = open(".gitignore").read() if os.path.exists(".gitignore") else "node_modules\ndist\n"
missing = [e for e in (".vercel", ".env", ".env.*", ".local/")
           if not any(line.strip() == e for line in gi.splitlines())]
if missing:
    if not gi.endswith("\n"): gi += "\n"
    gi += "\n# Deployment\n" + "\n".join(missing) + "\n"
open(".gitignore","w").write(gi)
print("de-replited", sys.argv[1])
