#!/usr/bin/env python3
"""De-Replit a standard Replit fullstack template (Express+Vite single server)."""
import json, re, sys, os

os.chdir(sys.argv[1])

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
gi = open(".gitignore").read() if os.path.exists(".gitignore") else "node_modules\ndist\n"
if ".vercel" not in gi:
    gi += "\n# Deployment\n.vercel\n.env\n.env.*\n.local/\n"
open(".gitignore","w").write(gi)
print("de-replited", sys.argv[1])
