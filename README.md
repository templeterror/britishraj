# britishraj

Next.js frontend, FastAPI backend. Clerk is the sign-in system. Supabase trusts Clerk session tokens, so database access follows the signed-in user.

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

Both developers share one Clerk **development** instance and one Supabase project. That keeps users and data the same on both machines. Production keys stay out of local env files.

## First time on a machine

1. Get the shared development values from the team password manager.
2. Run `./scripts/setup-env.sh`. This creates `frontend/.env.local` and `backend/.env` if they are not there yet. It will not overwrite a file you already filled in.
3. Paste the values into those two files. The placeholders say where each one comes from.
4. Run `./scripts/check-env.sh`.

`frontend/.env` is committed and only holds non-secret defaults (local API URL and Clerk route paths). Anything secret is gitignored.

## One-time project setup

Do this once for the shared project, not once per developer.

1. In the [Clerk Dashboard](https://dashboard.clerk.com), open the development instance and activate the [Supabase integration](https://clerk.com/docs/guides/development/integrations/databases/supabase). Copy the Clerk domain into `CLERK_DOMAIN`.
2. In the Supabase Dashboard, add Clerk under Authentication → Sign In / Providers → Third-party auth, and paste that same domain.
3. Copy the Clerk publishable and secret keys, the Supabase project URL, the publishable key, and the secret key into the password manager.

The Supabase secret key bypasses row level security. It belongs in `backend/.env` only.

## When a new variable is added

Add it to the example file and to `scripts/check-env.sh` in the same change. The other developer pulls, copies the new line into their local file, and re-runs the check.
