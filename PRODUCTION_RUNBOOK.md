# firmOS production runbook

## What is live in Supabase staging

The `firmos-demo` project has the finance action engine, Tally tables, manual GSTR-2B evidence, provider-native Zoho bank-match review, GST component storage, register projections, firm-scoped RLS, and private bank evidence storage.

## Private bank evidence

`20260712000008_private_bank_evidence.sql` is applied to staging. The `bank-statements` bucket is private. The backend stores new statements under a firm-scoped private object path and serves them only through `GET /api/bank-statements/{statement_id}/download`, which creates a five-minute signed link after firm authorization.

## Local development

Run the backend:

```bash
cd firmos-backend
STRICT_NO_MOCK=false FIRMOS_AUTH_MODE=dev uv run uvicorn api.main:app --host 127.0.0.1 --port 8001
```

Run the web app in another terminal:

```bash
cd apps/web
NEXT_PUBLIC_API_URL=http://127.0.0.1:8001 npm run dev -- --hostname 127.0.0.1 --port 3001
```

Open `http://127.0.0.1:3001`.

## Production configuration

The frontend belongs on Vercel with `apps/web` as its root directory. Its production environment needs:

- `NEXT_PUBLIC_API_URL=https://<your-api-domain>`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

The FastAPI backend must run on a separate HTTPS service; Vercel alone is not a suitable host for the current long-lived API and local Tally bridge model. Its production environment needs:

- `DATABASE_URL`
- `SUPABASE_JWT_SECRET`
- `TOKEN_ENC_KEY`
- `FIRMOS_AUTH_MODE=jwt`
- `STRICT_NO_MOCK=true`
- `ALLOWED_ORIGINS=https://<your-vercel-domain>`
- `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` for private bank evidence
- Zoho OAuth credentials and a production callback URL

Never put backend secrets, Zoho secrets, or the Supabase service key in Vercel's `NEXT_PUBLIC_*` variables.

## Release gate

Before enabling production users:

1. Authenticate GitHub and create/select the firmOS repository, then add it as this workspace's `origin` remote.
2. Deploy the backend to an HTTPS service and confirm `/health` plus JWT authentication.
3. Create the Vercel project, configure the frontend values above, and deploy.
4. Test Zoho OAuth, one purchase-bill creation, and one bank-match action in a real test organisation.
5. Test the local Tally bridge with a licensed test company.
6. Have a CA validate GSTR-3B treatment for RCM, reversals, exempt/zero-rated supplies, and ITC utilisation. Portal filing stays manual.
