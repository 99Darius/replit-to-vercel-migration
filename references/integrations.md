# Replit Integration Swaps (Phase 1, step 2)

Replit proxies many services through its sidecar/connectors (`REPLIT_SIDECAR_ENDPOINT`, `REPLIT_CONNECTORS_HOSTNAME`, `REPL_IDENTITY` token exchange). None work off-Replit. Swap each:

## OpenAI / LLMs — `AI_INTEGRATIONS_*` → real key

```ts
const apiKey = process.env.OPENAI_API_KEY ?? process.env.AI_INTEGRATIONS_OPENAI_API_KEY;
if (!apiKey) throw new Error("OPENAI_API_KEY must be set.");
export const openai = new OpenAI({
  apiKey,
  baseURL: process.env.AI_INTEGRATIONS_OPENAI_BASE_URL ?? undefined, // Replit proxy fallback
});
```
**Patch ALL copies** — barrel exports (`image/client.ts`, `audio/client.ts`) each re-validate `AI_INTEGRATIONS_*` at module load, so a missed one throws fatally on import. Drop `|| "default_key"` fallbacks. Anthropic/DeepSeek/xAI/etc. usually already use direct keys.

## Email — Replit Gmail connector → Resend

The connector code reads `REPL_IDENTITY` + `REPLIT_CONNECTORS_HOSTNAME` and `throw`s `X_REPLIT_TOKEN not found` off-Replit. Replace the transport, keep the caller signature:
```ts
export async function sendEmail(opts /* same shape as before */) {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) throw new Error("RESEND_API_KEY not set.");
  const from = process.env.EMAIL_FROM || "App <onboarding@resend.dev>";
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from, to: opts.to, subject: opts.subject, html: opts.body }),
  });
  if (!res.ok) throw new Error(`Resend failed (${res.status}): ${await res.text()}`);
}
```
`onboarding@resend.dev` only delivers to the Resend account owner — set `EMAIL_FROM` to a sender on a Resend-verified domain for real delivery. Plain SMTP / `nodemailer` with `GMAIL_USER`+`GMAIL_APP_PASSWORD` needs NO swap (no Replit dep) — just set the env vars.

## Object storage — Replit GCS sidecar → Vercel Blob

The sidecar uses `external_account` creds against `http://127.0.0.1:1106` (signed PUT URLs). Replace with Vercel Blob client-upload (bypasses the serverless body-size limit for large files):
```ts
// server: token handshake
import { handleUpload } from "@vercel/blob/client";
app.post("/api/.../upload", async (req, res) => {
  res.json(await handleUpload({
    body: req.body, request: req,
    onBeforeGenerateToken: async () => ({ allowedContentTypes: ["video/webm"], maximumSizeInBytes: 100*1024*1024 }),
    onUploadCompleted: async () => {},
  }));
});
```
```ts
// client: replace get-signed-URL + PUT with
import { upload } from "@vercel/blob/client";
const blob = await upload(fileName, fileBlob, { access: "public", handleUploadUrl: "/api/.../upload" });
// persist blob.url
```
Provision: `vercel blob create-store <name> --access public`, then `POST /v1/storage/stores/<id>/connections {projectId, envVarEnvironments:["production","preview","development"]}` → auto-injects `BLOB_READ_WRITE_TOKEN` (read implicitly by the SDK). Caveat: persistence relies on the client's follow-up write of `blob.url`; `onUploadCompleted` is the durable fallback if you need it.

## Google Sheets/Mail connector → service account

`getAccessToken()` via `REPL_IDENTITY` → standard service account:
```ts
const auth = new google.auth.GoogleAuth({
  credentials: JSON.parse(process.env.GOOGLE_SERVICE_ACCOUNT_KEY!),
  scopes: ["https://www.googleapis.com/auth/spreadsheets"],
});
```
Create a GCP service account, share the sheet with its email, set the JSON key in `GOOGLE_SERVICE_ACCOUNT_KEY`.

## Postgres — Replit "Production Database" is Neon

Already externally reachable + uses `@neondatabase/serverless`. Just provision a fresh Neon via `vercel integration add neon` and restore the dump; the driver code needs no change.
