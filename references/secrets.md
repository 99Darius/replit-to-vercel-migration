# Secret Extraction & Storage (Phase 1, step 4)

Replit secrets do NOT transfer. Extract from the running repl, store encrypted, never print full values.

## DB connection string

Workspace → Database pane → (pick Production Database) → Settings tab → Environment variables. `DATABASE_URL`, `PGHOST`, `PGUSER`, `PGPASSWORD`, etc. are in readable inputs. Dev + Prod are separate Neon instances — migrate Prod.

Robust grab (Playwright), dismissing the notification modal and clicking through to Settings:
```js
async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const findUrl = () => [...document.querySelectorAll('input,textarea')].map(e=>e.value||'').find(v=>v.startsWith('postgresql://'));
  for (let i=0;i<30;i++){
    const u=findUrl(); if(u) return {dbUrl:u};
    document.querySelector('button')&&[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Deny')?.click();
    [...document.querySelectorAll('button')].filter(b=>b.textContent.trim()==='Manage'&&b.className.includes('textButton')).pop()?.click();
    [...document.querySelectorAll('[role="tab"]')].find(t=>t.textContent.trim()==='Settings')?.click();
    await sleep(1500);
  }
}
```

## App Secrets pane

Newer Replit UI: the command palette "Secrets" search falls into FILE search. Instead open the **"+"/new-tab tools grid** → click the **Secrets** option.

Reveal-in-DOM doesn't expose values, but each row has a **"Copy secret value"** button. Override `navigator.clipboard.writeText` to capture what each copy writes:
```js
async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const captured = {}; let lastKey = null;
  const orig = navigator.clipboard.writeText.bind(navigator.clipboard);
  navigator.clipboard.writeText = (t) => { if(lastKey) captured[lastKey]=t; return Promise.resolve(); };
  for (const btn of [...document.querySelectorAll('button')].filter(b=>(b.getAttribute('aria-label')||'')==='Copy secret value')) {
    let row=btn,label=null;
    for(let up=0;up<8&&!label;up++){ row=row.parentElement; if(!row)break;
      label=[...row.querySelectorAll('div,span,code')].map(e=>e.textContent.trim()).find(t=>/^[A-Z][A-Z0-9_]{2,45}$/.test(t)); }
    lastKey=label; ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t=>btn.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true}))); await sleep(450);
  }
  navigator.clipboard.writeText = orig;
  return captured;   // key→value map
}
```
(Alternative: open the repl Shell tool and `printenv KEY1 KEY2 ...` — but the Shell tab is finicky to focus via Playwright; clipboard override is more reliable.)

## Storage: encrypted file + macOS Keychain passphrase

Shared LLM keys reused across many apps → one encrypted file any session can decrypt:
```bash
PASS=$(openssl rand -base64 32)
security add-generic-password -U -a "$USER" -s <service-name> -w "$PASS"
printf "%s" "$PASS" | openssl enc -aes-256-cbc -pbkdf2 -pass stdin -in keys.env -out keys.env.enc
# decrypt anywhere:
security find-generic-password -s <service-name> -w | \
  openssl enc -d -aes-256-cbc -pbkdf2 -pass stdin -in keys.env.enc
```
Per-app secrets (OAuth client secrets, admin hashes): same pattern, separate `.enc` file. **Never echo full secret values** to the terminal — pipe directly into `vercel env add` or the encrypt step. When handling tokens, print only prefix/length.

## Into Vercel

```bash
printf "%s" "$VALUE" | vercel env add <KEY> production
```
Generate fresh `SESSION_SECRET` (`openssl rand -hex 32`) rather than reusing the repl's.
