# Deployment guide

Four things to set up, in an order that lets you stop at any point and still
have something working:

1. [Local development](#1-local-development)
2. [The demo on GitHub Pages](#2-the-demo-on-github-pages) — publishable today, no accounts
3. [The custom domain](#3-the-custom-domain)
4. [The API and live mailing](#4-the-api) — the part that needs your credentials

Steps 1 and 2 need nothing from you. Step 3 needs your DNS. Step 4 needs a
Lob account, a Stripe account, and a host.

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

## 2. The demo on GitHub Pages

**In the repository, once:**

1. Settings → Pages → **Source: GitHub Actions**.
2. Push to `main`.

That is the whole setup. The workflow builds the frontend and publishes it at
`https://<owner>.github.io/<repo>/`, in demo mode, because `API_BASE_URL` is
unset.

### How the base path is handled

GitHub Pages serves a project site from a sub-path, which breaks naïvely built
assets. The workflow resolves it automatically:

| Where it is served | `VITE_BASE_PATH` | Set by |
|---|---|---|
| `https://<owner>.github.io/<repo>/` | `/<repo>/` | the workflow, when `CUSTOM_DOMAIN` is unset |
| `https://www.whyisthislighton.com/` | `/` | the workflow, when `CUSTOM_DOMAIN` is set |

Everything in the app that builds an asset URL uses `import.meta.env.BASE_URL`,
and CI asserts that a project-page build actually emits `/<repo>/assets/…`.

### Why routing works without any rewrite rules

The app uses hash routing: `…/#/create` is one document plus a fragment. Pages
serves the same `index.html` for it whatever the path, so there is no 404
redirect trick, no `404.html` copy, and no difference in behaviour between the
project URL and the custom domain. Deep links, refreshes and shared URLs all
work.

`.nojekyll` is written into the build so Pages does not run Jekyll and discard
Vite's underscore-prefixed files.

---

## 3. The custom domain

**1. Add the repository variable.** Settings → Secrets and variables → Actions →
Variables → New variable:

```
CUSTOM_DOMAIN = www.whyisthislighton.com
```

The next deploy writes a `CNAME` file into the build and switches the base path
to `/`.

**2. Point DNS at GitHub.** At your registrar, for the apex domain and the `www`
subdomain:

```
# www — a CNAME to your Pages host
www.whyisthislighton.com.   CNAME   <owner>.github.io.

# apex — four A records (and the AAAA records if you want IPv6)
whyisthislighton.com.       A       185.199.108.153
whyisthislighton.com.       A       185.199.109.153
whyisthislighton.com.       A       185.199.110.153
whyisthislighton.com.       A       185.199.111.153
```

> Check GitHub's current Pages IP addresses before you paste these; GitHub
> publishes them in *Managing a custom domain for your GitHub Pages site*. They
> change rarely, but they do change.

**3. Set it in GitHub too.** Settings → Pages → Custom domain →
`www.whyisthislighton.com` → Save. Wait for the DNS check to pass, then tick
**Enforce HTTPS**. The certificate is issued by GitHub automatically and can
take up to an hour on first setup.

**4. Decide which host is canonical.** Serving both the apex and `www` is fine;
GitHub redirects one to the other based on what you entered as the custom
domain. Whichever you choose must match `CUSTOM_DOMAIN` and must be in the
API's `CORS_ALLOW_ORIGINS`.

---

## 4. The API

Everything below this line is only needed for live mailing. The demo does not
use any of it.

### 4a. Choose a host

The API is a standard container: `backend/Dockerfile`, listening on `$PORT`,
with a `/api/v1/health` endpoint for health checks. Anything that runs
containers works. Two that fit this shape well:

**Fly.io** — good if you want the database and the app in one place, and the
cheapest way to keep a small always-on service.

```bash
cd backend
fly launch --no-deploy                 # creates fly.toml; pick a region near your users
fly postgres create --name wittl-db    # or bring your own PostgreSQL
fly postgres attach wittl-db           # sets DATABASE_URL
fly secrets set \
  APP_MODE=live \
  ADDRESS_PEPPER="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  CORS_ALLOW_ORIGINS=https://www.whyisthislighton.com \
  MAIL_PROVIDER=lob LOB_API_KEY=... LOB_WEBHOOK_SECRET=... \
  PAYMENT_PROVIDER=stripe STRIPE_SECRET_KEY=... STRIPE_WEBHOOK_SECRET=...
fly deploy
fly ssh console -C "alembic upgrade head"
```

**Render** — good if you prefer a dashboard and a managed PostgreSQL with
automatic backups. Create a Web Service from `backend/`, choose Docker, add a
PostgreSQL instance, set the environment variables in the dashboard, and set the
pre-deploy command to `alembic upgrade head`.

Whichever you choose: **run migrations as a release step, not in the container's
entrypoint.** Two replicas racing to migrate on every deploy is a bad day.

### 4b. Get a mailing provider

[Lob](https://lob.com) is what the integration targets, because it does the
three things this service needs from one vendor: US first-class letters, USPS
address verification, and signed delivery-status webhooks.

1. Create an account. You get a **test** key (`test_…`) and a **live** key
   (`live_…`). Start with test.
2. Dashboard → Webhooks → add an endpoint at
   `https://<your-api>/api/v1/webhooks/mail`, subscribed to the `letter.*`
   events. Copy the signing secret into `LOB_WEBHOOK_SECRET`.
3. Set a return address. Lob requires one on the envelope; the app uses the
   `RETURN_*` variables and **never** a sender's address. Use a PO box or a
   business address you are willing to publish, because it is printed on every
   letter and is how a recipient can write back.

`LOB_USE_TEST_KEY_ONLY=true` is a deliberate guard rail: while it is true, the
app refuses to start with a `live_` key. Set it to `false` only when you
genuinely intend to put paper in the mail.

### 4c. Get Stripe working, in test mode

1. Stripe → Developers → API keys → copy the **test** secret key
   (`sk_test_…`) into `STRIPE_SECRET_KEY`.
2. Developers → Webhooks → add an endpoint at
   `https://<your-api>/api/v1/webhooks/payments`, subscribed to:
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

### 4d. Point the frontend at it

Repository → Settings → Secrets and variables → Actions → Variables:

```
API_BASE_URL = https://api.whyisthislighton.com
```

The next deploy publishes in live mode. The workflow's summary says which mode
it published, on every run.

### 4e. Turn on bot protection

Once real money is involved, set `TURNSTILE_SECRET_KEY` to a
[Cloudflare Turnstile](https://developers.cloudflare.com/turnstile/) secret. It
is a no-op while blank; once set, the draft endpoint requires a valid token.

---

## Switching from demo to live: the checklist

| # | Step | Where |
|---|---|---|
| 1 | Generate a permanent `ADDRESS_PEPPER` | your host's secrets |
| 2 | `MAIL_PROVIDER=lob` with a **test** key | your host's secrets |
| 3 | `PAYMENT_PROVIDER=stripe` with **test** keys | your host's secrets |
| 4 | Set both webhook endpoints and their signing secrets | Lob + Stripe dashboards |
| 5 | Set the `RETURN_*` address | your host's secrets |
| 6 | Fill in the `[ … ]` placeholders on the Privacy and Terms pages | `frontend/src/routes/Legal.tsx` |
| 7 | Check the prices against Lob's current rates | `PRICE_*` variables |
| 8 | Send yourself a test letter, end to end | your own address |
| 9 | `APP_MODE=live`, `LOB_USE_TEST_KEY_ONLY=false`, live keys | your host's secrets |
| 10 | Set `API_BASE_URL` in the GitHub repository variables | GitHub |

The app refuses to start if step 9 is done without steps 1–5, which is the
intended behaviour: it should not be possible to have a deployment that takes
money and posts nothing.

> **`ADDRESS_PEPPER` is permanent.** It is the HMAC key for the address hashes
> that enforce the cooldown and the do-not-mail list. Changing it orphans every
> existing record, meaning someone who asked never to be written to again could
> receive another letter. Generate it once and keep it safe.

---

## Environment variables

### Frontend — all public, all inlined into the bundle

| Variable | Default | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | *(empty)* | Empty = demo mode. Set to the API origin, no trailing slash. |
| `VITE_BASE_PATH` | `/` | Set by the deploy workflow. |
| `VITE_CONTACT_EMAIL` | `hello@whyisthislighton.com` | Shown on the privacy page. |

Nothing secret goes here, ever. Vite inlines these into JavaScript that anyone
can read with View Source, and both CI and the deploy workflow fail the build if
a key-shaped string appears in `dist/`.

### Backend

| Variable | Default | Notes |
|---|---|---|
| `APP_MODE` | `demo` | `live` enables the startup checks below. |
| `DATABASE_URL` | SQLite file | PostgreSQL in production. |
| `CORS_ALLOW_ORIGINS` | `http://localhost:5173` | Comma-separated exact origins. Wildcards are rejected at startup. |
| `ADDRESS_PEPPER` | dev value | **Permanent.** See the warning above. |
| `MAIL_PROVIDER` | `mock` | `mock` or `lob`. |
| `LOB_API_KEY` / `LOB_WEBHOOK_SECRET` | — | Required when `MAIL_PROVIDER=lob`. |
| `LOB_USE_TEST_KEY_ONLY` | `true` | While true, a `live_` key is refused. |
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
- a missing `LOB_API_KEY`, `LOB_WEBHOOK_SECRET`, or `RETURN_*` address
- a missing `STRIPE_SECRET_KEY` or `STRIPE_WEBHOOK_SECRET`
- the default `ADDRESS_PEPPER`
- a mailing provider that cannot send real mail (a test key, in live mode)
- a payment provider that *can* charge real money paired with one that cannot mail
- a wildcard in `CORS_ALLOW_ORIGINS`

---

## Operating it

### Recurring jobs

Two things want a schedule. Neither is urgent enough to need a queue.

```bash
# Every 10 minutes: pick up letters that were paid for but not submitted,
# usually because a worker died mid-submission. Safe to run concurrently.
python -c "
from app.db.session import session_scope
from app.core.config import get_settings
from app.providers.factory import get_providers
from app.services import mailing
mail, payments = get_providers()
with session_scope() as db:
    for letter in mailing.find_retryable(db):
        mailing.submit_letter(db, settings=get_settings(), mail=mail, payments=payments, letter=letter)
"

# Daily: erase the personal data on letters past their retention date.
python -c "
from app.db.session import session_scope
from app.services import mailing
with session_scope() as db:
    print('purged', mailing.purge_expired(db))
"
```

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

**Assets 404 on the project URL.** `VITE_BASE_PATH` did not match. It should be
`/<repo>/` with both slashes. The workflow does this for you; check whether
`CUSTOM_DOMAIN` is set when it should not be.

**The custom domain serves the old project-path build.** Pages caches
aggressively. Re-run the deploy workflow after setting `CUSTOM_DOMAIN`, and
confirm the `CNAME` file is present in the artifact.

**Browser console: blocked by CORS.** The site's origin is not in
`CORS_ALLOW_ORIGINS` on the API. It must match exactly, including scheme and
subdomain — `https://www.whyisthislighton.com` and
`https://whyisthislighton.com` are two different origins.

**Payments succeed but no letter is submitted.** Look at the webhook deliveries
in the Stripe dashboard. A 400 from `/api/v1/webhooks/payments` means the
signature check failed — almost always the wrong `STRIPE_WEBHOOK_SECRET`, or a
proxy that modified the request body. The body must reach the app byte-for-byte.

**Letters stuck in `submitting`.** A worker died between claiming the letter and
hearing back from Lob. The retry job clears these, and Lob's idempotency key
(the letter id) means a retry cannot produce a second envelope.

**The app will not start and says it is refusing.** Read the message; it lists
every problem it found. This is the check working.
