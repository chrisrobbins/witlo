# Deployment guide

Everything runs from **one Vercel project**: the static frontend and the Python
API are the same deployment, served from the same domain, so there is no CORS
and one dashboard. Four steps, in an order that lets you stop at any point and
still have something working:

1. [Local development](#1-local-development)
2. [Deploy to Vercel](#2-deploy-to-vercel) — the demo, publishable today with no accounts
3. [The custom domain](#3-the-custom-domain)
4. [Going live: PostGrid and Stripe](#4-going-live-postgrid-and-stripe) — the part that needs your credentials

Steps 1 and 2 need nothing from you. Step 3 needs your DNS. Step 4 needs a
PostGrid account, a Stripe account, and a Postgres database (Neon).

---

## 1. Local development

```bash
git clone <your repo> && cd whyisthislighton
cd frontend && npm install && npm run dev
```

`http://localhost:5173` now serves the full demo. To run the API too:

```bash
cp backend/.env.example backend/.env
docker compose up --build
docker compose exec api alembic upgrade head
echo 'VITE_API_BASE_URL=http://localhost:8000' > frontend/.env.local
```

The defaults in `.env.example` are demo-safe: mock providers, no credentials,
nothing that can post a letter.

---

## 2. Deploy to Vercel

`vercel.json` at the repo root already describes the whole thing: build the
frontend, serve it from the root, route `/api/*` to the Python function in
`api/index.py` (which imports the FastAPI app from `backend/`), and run the two
recurring jobs on a cron.

**Once:**

1. [vercel.com/new](https://vercel.com/new) → import the GitHub repo.
2. Leave the framework preset as detected and the root directory as `./`. Vercel
   reads `vercel.json` for the build command and output directory; don't
   override them.
3. Set the **Python Version** to 3.12 (Project → Settings → General).
4. Environment variables (Project → Settings → Environment Variables). For the
   demo, only two, in **all** environments:

   ```
   VITE_API_BASE_URL = /
   VITE_CONTACT_EMAIL = hello@whyisthislighton.com
   ```

   `VITE_API_BASE_URL=/` means "the API is on this same origin". Leave it unset
   and the build is a pure browser-only demo with no API at all — also fine, and
   the safe default.
5. Deploy. Every push to `main` redeploys production; every branch and PR gets
   its own preview URL with the same config.

That is the whole setup for the demo. `APP_MODE` defaults to `demo`, so the API
comes up in mock mode — it can compose and price a letter but the startup check
refuses to let it mail or charge anything. Section 4 turns that on.

### Routing

The frontend uses hash routing (`…/#/create` is one document plus a fragment),
so there are no SPA rewrite rules to configure — `index.html` is served for
every non-`/api` path and the fragment does the rest. Deep links, refreshes and
shared URLs all work.

---

## 3. The custom domain

**1.** Project → Settings → Domains → add `whyisthislighton.com` and
`www.whyisthislighton.com`. Pick one as primary; Vercel 308-redirects the other
to it.

**2.** Point DNS at Vercel as it instructs — usually an `A` record for the apex
to `76.76.21.21` and a `CNAME` for `www` to `cname.vercel-dns.com`. Vercel
verifies and issues the TLS certificate automatically, typically within minutes.

**3.** Because the API shares this origin, there is nothing else to change — no
`CORS_ALLOW_ORIGINS` to update, no second subdomain. If you later split the API
onto its own host, that is when CORS and a separate `api.` record come back.

---

## 4. Going live: PostGrid and Stripe

Everything below this line is only needed for real mailing. The demo does not
use any of it. The API is already deployed from step 2 — going live is adding
credentials and flipping `APP_MODE`.

### 4a. The database

Serverless functions have no disk, so SQLite is out. Add **Neon** from the
Vercel Marketplace (Project → Storage → Create Database → Neon) and it injects a
pooled `DATABASE_URL` into the project automatically. If you bring your own Neon
or Supabase project, use its **pooled** connection string (Neon's `-pooler`
host; Supabase port 6543) and set `DATABASE_URL` yourself, in the
`postgresql+psycopg://…` form.

Then create the schema — there is no shell, so use the migrate endpoint:

```bash
curl -X POST https://<your-app>/api/v1/internal/migrate \
  -H "Authorization: Bearer $CRON_SECRET"
```

Run it again after any deploy that adds a migration. (`CRON_SECRET` is set in
4d.)

### 4b. The recurring jobs

`vercel.json` already registers two crons against the project:

| Path | Schedule | What |
|---|---|---|
| `/api/v1/internal/submit-pending` | hourly | hand any paid-but-unmailed letter to PostGrid |
| `/api/v1/internal/purge-expired` | daily | erase personal data past `RETENTION_DAYS` |

They only work once `CRON_SECRET` is set (4d); Vercel sends it as a bearer token
automatically. `submit-pending` is a safety net — a letter is normally submitted
in the moment its payment webhook is processed — so on Vercel's Hobby plan, where
crons run once a day, the worst case is a stuck letter waiting a day for the
retry. On Pro the hourly schedule applies.

### 4c. Get a mailing provider

[PostGrid](https://postgrid.com) is what the integration targets: US first-class
letters printed from the rendered HTML, USPS address verification, and signed
delivery-status webhooks, on a self-serve account with no business-email
requirement.

1. Sign up at [postgrid.com/sign-up](https://www.postgrid.com/sign-up/) and pick
   the **Pay-Per-Piece** plan (no platform fee). Grab the **Print & Mail** API
   key — `test_sk_…` for the sandbox (letters are created but never printed),
   `live_sk_…` for production — and put it in `POSTGRID_API_KEY`.
2. *Optional but recommended:* PostGrid's **Address Verification** is a separate
   product with its own key. Enable it and put its key in `POSTGRID_AV_API_KEY`
   for real CASS/DPV verification. Left blank, the app verifies by creating a
   Print & Mail contact and reading its `addressStatus` — which is real on a
   `live_sk_` key but marks everything `verified` in the sandbox.
3. Dashboard → Webhooks → add an endpoint at
   `https://<your-api>/api/v1/webhooks/mail`, subscribed to `letter.created` and
   `letter.updated`. **Set the payload format to JSON**, not the JWT default.
   Copy the signing secret into `POSTGRID_WEBHOOK_SECRET`.
4. Set a return address. PostGrid requires one on the envelope; the app uses the
   `RETURN_*` variables and **never** a sender's address. Use a PO box or a
   business address you are willing to publish, because it is printed on every
   letter and is how a recipient can write back.

`POSTGRID_USE_TEST_KEY_ONLY=true` is a deliberate guard rail: while it is true,
the app refuses to start with a `live_` key. Set it to `false` only when you
genuinely intend to put paper in the mail.

PostGrid has no local webhook-forwarding CLI. To exercise `/api/v1/webhooks/mail`
before deploying, expose the local API with a tunnel
(`cloudflared tunnel --url http://localhost:8000`) and point a sandbox webhook at
`https://<tunnel>/api/v1/webhooks/mail`. Address verification and letter
creation work against `localhost` directly with a `test_sk_…` key.

### 4d. Get Stripe working, in test mode

1. Stripe → Developers → API keys → copy the **test** secret key
   (`sk_test_…`) into `STRIPE_SECRET_KEY`.
2. Developers → Webhooks → add an endpoint at
   `https://<your-app>/api/v1/webhooks/payments`, subscribed to:
   - `checkout.session.completed`
   - `checkout.session.async_payment_succeeded`
   - `checkout.session.async_payment_failed`
   - `checkout.session.expired`
   - `charge.refunded`

   Copy the signing secret into `STRIPE_WEBHOOK_SECRET`.
3. Test locally with the Stripe CLI:

   ```bash
   stripe listen --forward-to localhost:8000/api/v1/webhooks/payments
   # use the whsec_… it prints as STRIPE_WEBHOOK_SECRET
   stripe trigger checkout.session.completed
   ```

Card `4242 4242 4242 4242` with any future expiry completes a test payment.

**The success redirect does not send mail.** Only the verified webhook does. You
can prove this to yourself by completing a test payment with the webhook
endpoint disabled: the browser shows a receipt page that says *waiting on
payment*, and no letter is submitted.

### 4e. The Vercel environment variables

Project → Settings → Environment Variables. Server-side values (everything
except the two `VITE_*` ones) belong in **Production** only unless you also want
previews hitting real providers.

```
APP_MODE                 = live          # keep at demo until 4f is done
DATABASE_URL             = <from Neon; pooled>   # skip if the Neon integration set it
ADDRESS_PEPPER           = <permanent; python -c "import secrets;print(secrets.token_urlsafe(48))">
CORS_ALLOW_ORIGINS       = https://whyisthislighton.com,https://www.whyisthislighton.com
CRON_SECRET              = <python -c "import secrets;print(secrets.token_urlsafe(32))">

MAIL_PROVIDER            = postgrid
POSTGRID_API_KEY         = live_sk_…
POSTGRID_AV_API_KEY      = live_sk_…     # optional; blank = verify via a contact
POSTGRID_WEBHOOK_SECRET  = <from the PostGrid webhook, JSON format>
POSTGRID_USE_TEST_KEY_ONLY = false       # only when you mean it

PAYMENT_PROVIDER         = stripe
STRIPE_SECRET_KEY        = sk_live_…
STRIPE_WEBHOOK_SECRET    = whsec_…
CHECKOUT_SUCCESS_URL     = https://whyisthislighton.com/#/receipt?letter={LETTER_ID}
CHECKOUT_CANCEL_URL      = https://whyisthislighton.com/#/create

RETURN_NAME  = Why Is This Light On?
RETURN_LINE1 = …
RETURN_CITY  = …
RETURN_STATE = …
RETURN_ZIP   = …

TURNSTILE_SECRET_KEY     = <see 4f>
```

The two build-time frontend values (`VITE_API_BASE_URL=/`, `VITE_CONTACT_EMAIL`)
from step 2 stay as they are. Redeploy after changing any variable — Vercel does
not apply them to the running deployment retroactively.

### 4f. Turn on bot protection

Once real money is involved, set `TURNSTILE_SECRET_KEY` to a
[Cloudflare Turnstile](https://developers.cloudflare.com/turnstile/) secret. It
is a no-op while blank; once set, the draft endpoint requires a valid token.

---

## Switching from demo to live: the checklist

| # | Step | Where |
|---|---|---|
| 1 | Add Neon; run `POST /api/v1/internal/migrate` | Vercel Storage + curl |
| 2 | Generate a permanent `ADDRESS_PEPPER` and a `CRON_SECRET` | Vercel env vars |
| 3 | `MAIL_PROVIDER=postgrid` with **test** keys (Print & Mail, + Address Verification) | Vercel env vars |
| 4 | `PAYMENT_PROVIDER=stripe` with **test** keys | Vercel env vars |
| 5 | Set both webhook endpoints and their signing secrets (PostGrid webhook: JSON format) | PostGrid + Stripe dashboards |
| 6 | Set the `RETURN_*` address | Vercel env vars |
| 7 | Fill in the `[ … ]` placeholders on the Privacy and Terms pages | `frontend/src/routes/Legal.tsx` |
| 8 | Check the prices against PostGrid's current rates | `PRICE_*` variables |
| 9 | Send yourself a test letter, end to end | your own address |
| 10 | `APP_MODE=live`, `POSTGRID_USE_TEST_KEY_ONLY=false`, live keys, redeploy | Vercel env vars |

The app refuses to start if step 10 is done without steps 2–6, which is the
intended behaviour: it should not be possible to have a deployment that takes
money and posts nothing.

> **`ADDRESS_PEPPER` is permanent.** It is the HMAC key for the address hashes
> that enforce the cooldown and the do-not-mail list. Changing it orphans every
> existing record, meaning someone who asked never to be written to again could
> receive another letter. Generate it once and keep it safe.

---

## Environment variables

### Frontend — build-time, all public, all inlined into the bundle

| Variable | Default | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | *(empty)* | Empty = demo mode. `/` = same-origin API (the Vercel deployment). A full origin for a separately hosted API. |
| `VITE_BASE_PATH` | `/` | Served from the domain root; only change to host the static build under a sub-path. |
| `VITE_CONTACT_EMAIL` | `hello@whyisthislighton.com` | Shown on the privacy page. |

Nothing secret goes here, ever. Vite inlines these into JavaScript that anyone
can read with View Source, and CI fails the build if a key-shaped string appears
in `dist/`.

### Backend — Vercel Environment Variables (Production)

| Variable | Default | Notes |
|---|---|---|
| `APP_MODE` | `demo` | `live` enables the startup checks below. |
| `DATABASE_URL` | SQLite file | A **pooled** Postgres URL in production (`postgresql+psycopg://…`). Set by the Neon integration. |
| `CRON_SECRET` | *(empty)* | Bearer token for `/api/v1/internal/*`. Blank disables that router. Vercel Cron sends it automatically. |
| `CORS_ALLOW_ORIGINS` | `http://localhost:5173` | Comma-separated exact origins. Wildcards are rejected at startup. Unused when the frontend and API share an origin. |
| `ADDRESS_PEPPER` | dev value | **Permanent.** See the warning above. |
| `MAIL_PROVIDER` | `mock` | `mock` or `postgrid`. |
| `POSTGRID_API_KEY` / `POSTGRID_WEBHOOK_SECRET` | — | Required when `MAIL_PROVIDER=postgrid`. Webhook must be JSON format. |
| `POSTGRID_AV_API_KEY` | — | PostGrid's separate Address Verification key. Blank = reuse `POSTGRID_API_KEY`. |
| `POSTGRID_USE_TEST_KEY_ONLY` | `true` | While true, a `live_` key is refused. |
| `RETURN_NAME` / `RETURN_LINE1` / `RETURN_LINE2` / `RETURN_CITY` / `RETURN_STATE` / `RETURN_ZIP` | — | The service's own return address. Never a sender's. |
| `PAYMENT_PROVIDER` | `none` | `none`, `mock` or `stripe`. |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | — | Required when `PAYMENT_PROVIDER=stripe`. |
| `CHECKOUT_SUCCESS_URL` / `CHECKOUT_CANCEL_URL` | site URLs | `{LETTER_ID}` is substituted server-side. |
| `PRICE_POSTAGE_CENTS` / `PRICE_PRINTING_CENTS` / `PRICE_SERVICE_CENTS` | 174 / 95 / 80 | **Check against your provider's current rates.** |
| `REPEAT_ADDRESS_COOLDOWN_DAYS` | `180` | Before the same address may be written to again. |
| `MAX_LETTERS_PER_ADDRESS_LIFETIME` | `3` | A hard ceiling regardless of cooldown. |
| `RATE_LIMIT_PER_IP_PER_HOUR` | `12` | Address checks and suppressions. |
| `RATE_LIMIT_DRAFTS_PER_IP_PER_DAY` | `30` | Draft creation. |
| `RETENTION_DAYS` | `90` | Then the address, letter text and email are erased. |
| `TURNSTILE_SECRET_KEY` | *(empty)* | Blank disables the human check. |

### What "live mode" refuses to start with

- `MAIL_PROVIDER=mock` — it would take money and mail nothing
- `PAYMENT_PROVIDER=mock` — it would mail letters nobody paid for
- a missing `POSTGRID_API_KEY`, `POSTGRID_WEBHOOK_SECRET`, or `RETURN_*` address
- a missing `STRIPE_SECRET_KEY` or `STRIPE_WEBHOOK_SECRET`
- the default `ADDRESS_PEPPER`
- a mailing provider that cannot send real mail (a test key, in live mode)
- a payment provider that *can* charge real money paired with one that cannot mail
- a wildcard in `CORS_ALLOW_ORIGINS`

---

## Operating it

### Recurring jobs

Two, both registered as crons in `vercel.json` and run as HTTP endpoints
(`app/api/internal.py`) because a serverless deployment has no worker process:

| Endpoint | Cron | Purpose |
|---|---|---|
| `POST /api/v1/internal/submit-pending` | hourly | pick up letters paid for but not yet handed to PostGrid, or stuck mid-submission — a safety net for the inline submission |
| `POST /api/v1/internal/purge-expired` | daily | blank the address, letter text and email on letters past `RETENTION_DAYS` |

Both require `Authorization: Bearer $CRON_SECRET`; Vercel adds it automatically.
To run one by hand: `curl -X POST https://<app>/api/v1/internal/submit-pending -H "Authorization: Bearer $CRON_SECRET"`.
There is also `POST /api/v1/internal/migrate` (`alembic upgrade head`) for the
same "no shell" reason.

> Vercel Hobby runs each cron **once a day** regardless of the schedule. That is
> fine for `purge-expired` and acceptable for `submit-pending` (a stuck letter
> waits up to a day for the retry; the common path submits immediately on the
> payment webhook). Pro honours the hourly schedule.

### When a letter fails after payment

The app handles this without you. A retryable provider error returns the letter
to `paid` for the retry job; after four attempts, or on a permanent rejection,
it refunds in full through Stripe and records why. The receipt page then says
*Not mailed* and explains what happened. If the refund itself fails, the letter's
`status_detail` says a person needs to do it by hand — search for letters in
`failed` with `refunded_at IS NULL`.

### If a recipient asks to be left alone

They can do it themselves at `/#/no-more-letters`, and that is the path to point
them at. It writes a hash of the address to the suppression list, which is
checked when a draft is created *and again* immediately before printing — so a
letter already paid for still gets stopped and refunded.

There is deliberately no way to remove an address from that list through the
site.

---

## Troubleshooting

**`/api/*` returns 404 on Vercel.** The Python function did not build or the
rewrite is not matching. Check the deployment's Functions tab for `api/index.py`
and its build log; a `ModuleNotFoundError` there usually means `requirements.txt`
at the repo root did not resolve, or `includeFiles` did not carry `backend/`.

**The frontend loads but every API call fails.** `VITE_API_BASE_URL` was not set
to `/` for that environment, so the build is still in demo mode (or is pointed
at the wrong origin). It is a build-time value — redeploy after changing it.

**Browser console: blocked by CORS.** Only happens if the API is on a different
origin than the site. Add that origin to `CORS_ALLOW_ORIGINS` exactly, including
scheme and subdomain — `https://www.whyisthislighton.com` and
`https://whyisthislighton.com` are two different origins.

**A cron endpoint returns 404.** `CRON_SECRET` is not set, which disables the
whole `/api/v1/internal/*` router. A 401 there means the token is wrong.

**Payments succeed but no letter is submitted.** Look at the webhook deliveries
in the Stripe dashboard. A 400 from `/api/v1/webhooks/payments` means the
signature check failed — almost always the wrong `STRIPE_WEBHOOK_SECRET`, or a
proxy that modified the request body. The body must reach the app byte-for-byte.

**Letters stuck in `submitting`.** A worker died between claiming the letter and
hearing back from PostGrid. The retry job clears these, and the `Idempotency-Key`
(the letter id) means a retry cannot produce a second envelope.

**Mail webhook returns 400.** The signature did not verify. Usual causes: the
wrong `POSTGRID_WEBHOOK_SECRET`, or the webhook was created in PostGrid's default
JWT payload format — this integration needs it set to **JSON**.

**The app will not start and says it is refusing.** Read the message; it lists
every problem it found. This is the check working.
