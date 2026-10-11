# Deploy the backend on Railway

The FastAPI app lives in this folder. Railway builds `Dockerfile`, starts uvicorn on Railway's `PORT`, and checks `GET /health`.

The public site stays on Vercel (`https://britishraj.vercel.app`). This service is only the API.

## 1. Put these files on GitHub

Railway builds from GitHub, not from your laptop. Commit and push this folder, including:

- `Dockerfile`
- `railway.toml`
- `.dockerignore`
- `app/main.py`
- `requirements.txt`

Leave `backend/.env` and `backend/KEYS.md` untracked. They are gitignored on purpose.

## 2. Create the service

1. Sign in at [railway.com](https://railway.com).
2. Choose **New Project**, then **Deploy from GitHub repo**.
3. Pick `templeterror/britishraj`.
4. When Railway asks which directory to use, set the root directory to `backend`.

If the service was already created from the repository root, open the service, then **Settings → Source → Root Directory**, set it to `backend`, and save. The repo root has no Python app. A build from `/` finishes without this API.

`railway.toml` in this folder tells Railway to use the Dockerfile and to call:

```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
```

Do not set `PORT` yourself. Railway assigns it.

## 3. Add variables

Open the service, then **Variables**, and add these. Use the same Clerk development instance and the same Supabase project as the Vercel frontend. `settings.py` rejects `pk_live_` and `sk_live_` keys.

| Variable | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `FRONTEND_ORIGIN` | `https://britishraj.vercel.app` |
| `CLERK_PUBLISHABLE_KEY` | Same `pk_test_…` key as Vercel `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` |
| `CLERK_SECRET_KEY` | Same `sk_test_…` key as Vercel `CLERK_SECRET_KEY` |
| `CLERK_DOMAIN` | Clerk domain only, such as `happy-penguin-12.clerk.accounts.dev`. No `https://` |
| `SUPABASE_URL` | Same project URL as Vercel `NEXT_PUBLIC_SUPABASE_URL` |
| `SUPABASE_PUBLISHABLE_KEY` | Same publishable key as the frontend |
| `SUPABASE_SECRET_KEY` | Supabase secret key. This service only. Never put it on Vercel with a `NEXT_PUBLIC_` name |
| `XAI_API_KEY` | xAI API key from console.x.ai (`xai-…`). Required for the intake, analyst, and advisor agents. Optional for `/health`. See `backend/KEYS.md` |

To let a local frontend call this API as well, set `FRONTEND_ORIGIN` to both origins, comma-separated:

```text
https://britishraj.vercel.app,http://localhost:3000
```

Railway restarts the service when you save variables.

## 4. Open a public URL

1. Open the service, then **Settings → Networking**.
2. Click **Generate Domain**.
3. Copy the `https://….up.railway.app` URL. No trailing slash.

## 5. Check the deploy

Wait until the deployment is **Active**, then open:

```text
https://YOUR-RAILWAY-DOMAIN/health
```

A healthy service looks like this:

```json
{"ok": true, "missing": [], "xai": true}
```

`ok` means the process is running. `missing` lists required variable names that are still empty. `xai` is true when `XAI_API_KEY` is set.

## 6. Point the Vercel app at Railway

The frontend reads `NEXT_PUBLIC_API_URL` at build time. The committed default is `http://localhost:8000`, which is correct on a laptop and wrong in production.

1. Vercel → the `britishraj` project → **Settings → Environment Variables**.
2. Add `NEXT_PUBLIC_API_URL` for Production and Preview.
3. Set it to the Railway URL from step 4, with `https://` and no trailing slash.
4. Redeploy the frontend. The deployment that is already live still has the old value until you redeploy.

## 7. Ship a later change

Push to the branch Railway is watching. Railway builds again from `backend/`. Variable changes apply on the next restart and do not need a new git commit.
