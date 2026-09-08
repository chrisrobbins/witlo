# Status: what works, what was tested, what needs you

Written to be read before you trust anything here. Where something was not
verified, it says so.

---

## The short version

The demo is finished and can be deployed to Vercel today. The API is
complete and its logic is tested; it has been exercised against PostGrid's
sandbox (verify, create, re-submit) but never against a live key or Stripe.
Nothing in this repository has printed a letter or moved any money.

---

## 1. What works

### The demo — complete, and the primary deliverable

| | |
|---|---|
| Landing page, an example letter, how-it-works, FAQ, "why lighting matters", privacy, terms, do-not-mail, 404 | ✅ |
| Four-step wizard: address → observations → suggestions → preview | ✅ |
| Client-side validation with per-field, plain-language messages | ✅ |
| Letter composed from the template, live, on every keystroke | ✅ |
| Full-page preview showing the exact letter and exact address | ✅ |
| Print / save as PDF — a clean page with no site furniture | ✅ |
| Download a self-contained HTML letter that works offline | ✅ |
| A clear, permanent statement that nothing will be mailed | ✅ |
| No payment control exists at all in demo mode | ✅ |
| Hash routing — deep links and refreshes work with no rewrite rules | ✅ |
| Same-origin API — the frontend and `/api/*` are one Vercel deployment, no CORS | ✅ |
| Keyboard operation, skip link, focus management between steps | ✅ |
| `prefers-reduced-motion`, WCAG AA contrast, 44px tap targets | ✅ |
| No horizontal scroll at 360px | ✅ |

### The API — complete, exercised against mock providers only

| | |
|---|---|
| Server-side address validation and provider verification | ✅ |
| Standardized-address confirmation before purchase | ✅ |
| Server-side pricing; the browser never proposes a price | ✅ |
| Letter recomposed server-side and compared to the sender's fingerprint | ✅ |
| Mailing-provider abstraction: deterministic mock + PostGrid | ✅ (PostGrid unexercised against the live API) |
| Payment abstraction: mock + Stripe Checkout | ✅ (Stripe unexercised) |
| Stripe and PostGrid webhook signature verification | ✅ tested thoroughly |
| Duplicate-event protection (unique constraint, not a query) | ✅ |
| Idempotent checkout (stored response per key) | ✅ |
| Idempotent submission (letter id as the provider's key) | ✅ |
| State machine: draft → pending_payment → paid → submitting → submitted → provider statuses, plus failed and canceled | ✅ |
| Retry with backoff attempts, then refund | ✅ |
| Repeat-address cooldown and a lifetime cap | ✅ |
| Do-not-mail list, checked at draft time *and* before printing | ✅ |
| Database-backed rate limiting (survives restarts, holds across instances) | ✅ |
| Log redaction for addresses, ZIPs and emails | ✅ |
| Retention: personal data erased, hash and outcome kept | ✅ |
| Startup checks that refuse unsafe configurations | ✅ |
| Alembic migrations | ✅ (schema created; see caveat below) |

---

## 2. What was tested, and how

### Automated

| Suite | Count | Runs where |
|---|---|---|
| pytest (`backend/tests`) | 146 tests | CI, and locally with `pip install -r requirements-dev.txt` |
| Vitest (`frontend/tests`) | 50 cases | CI, and locally with `npm test` |
| Browser checks (`tools/e2e-check.mjs`) | 75 checks | headless Chromium |
| TypeScript ↔ Python letter parity | 8 fixtures, byte-for-byte | both suites |

**Executed during this build:** 80 of the 146 pytest tests, and all 75 browser
checks — all passing. The remaining 66 pytest tests need SQLAlchemy, FastAPI and
pytest, which the build sandbox could not install (its network allowlist blocks
`pypi.org` and `registry.npmjs.org`). They are written and wired into CI, and
they will run on your first push. **The same constraint means the Vitest suite
and the Vite production build have not been executed either** — they are
likewise wired into CI. See §4.

### What the browser checks actually exercise

Not smoke tests. Each of these is a specific claim, verified in Chromium against
the real bundle:

- every route renders with no console error, including the 404
- an empty address is refused with a message per field, and `aria-invalid` is set
- a PO box is refused with an explanation, not a generic error
- a malformed ZIP is refused
- the note field appears only when "something else" is chosen
- a note containing legal or enforcement language is refused, with a reason
- a note containing a phone number is refused
- the preview shows the selected observations and *not* the unselected ones
- the note appears verbatim in the preview, exactly as it will print
- deselecting an observation removes it from the preview
- the downloaded file is a complete, self-contained, print-ready document
- the download is named after the address
- the street field is reachable by tab alone and accepts typed input
- a choice card toggles with the space bar
- the skip link is the first tab stop and becomes visible on focus
- no horizontal overflow at 390px and 360px, across five routes
- the primary call to action is at least 44px tall on a phone
- stars stop animating under `prefers-reduced-motion`
- 30 text elements meet WCAG AA contrast, with translucent backgrounds
  composited the way the browser paints them
- exactly one `<h1>` on each of nine routes
- each route sets its own document title

### Verified by eye

Screenshots at 1440px and 390px for every route, plus the print output rendered
to PDF at US Letter. Four defects were found this way and fixed: paragraphs in
the letter collapsing together (a CSS specificity bug), an empty right-hand
column on the preview step, mobile nav links below the tap-target minimum, and
the wizard having no `<h1>`. The printed letter was checked at both extremes —
a minimal letter and the longest one the template can produce.

### What is *not* tested

- **PostGrid — sandbox only.** Address verification, letter creation (with the
  return address and rendered HTML), and idempotent re-submission have all been
  run against PostGrid's real `test_sk_` sandbox and behave as the code expects;
  `expectedDeliveryDate` is not returned there and is handled as absent. What is
  *not* exercised: a `live_sk_` key, an actual printed letter, real CASS/DPV
  verification (the sandbox marks every address `verified`), and the delivery
  webhook against a live endpoint — the `letter.updated` / `imbStatus` mapping is
  covered only by offline unit tests. When wiring the webhook, set its payload
  format to **JSON**, not PostGrid's JWT default.
- **Stripe.** Same. Signature verification is thoroughly tested against the
  documented algorithm; `checkout.Session.create` has never been called.
- **A real letter.** Nothing has been printed or posted.
- **Alembic against PostgreSQL.** The migration is written and CI runs
  `upgrade → downgrade → upgrade` plus an autogenerate drift check, but that has
  not executed yet.
- **Load.** No performance testing. For the expected volume this is fine; if it
  ever is not, the rate-limit table is the first thing to watch.

---

## 3. What needs your accounts or credentials

Nothing here blocks the demo.

| # | What | Why | Where it goes |
|---|---|---|---|
| 1 | **A PostGrid account** (Pay-Per-Piece plan) | Printing, postage, address verification, delivery webhooks | `POSTGRID_API_KEY`, `POSTGRID_AV_API_KEY`, `POSTGRID_WEBHOOK_SECRET` |
| 2 | **A Stripe account** | Taking payment for postage | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` |
| 3 | **A Vercel project** | Hosts the frontend and the Python API together | one import at vercel.com/new |
| 4 | **A Neon Postgres database** | Serverless has no disk; production storage | `DATABASE_URL` (pooled) |
| 5 | **DNS for witlo.info** | The custom domain | Your registrar |
| 6 | **A return address you own** | PostGrid requires one, and it is printed on every letter | `RETURN_*` |
| 7 | **A generated `ADDRESS_PEPPER`** | Keys the address hashes. **Permanent** — changing it orphans every do-not-mail record | Your host's secrets |
| 8 | **A Cloudflare Turnstile key** *(recommended)* | Bot protection once money is involved | `TURNSTILE_SECRET_KEY` |

---

## 4. What needs a decision from you

### Decisions I made, that you may want to change

| Decision | What I chose | Why, and what to consider |
|---|---|---|
| **Mailing provider** | PostGrid | US first-class letters from the rendered HTML, USPS verification, and signed webhooks, on a self-serve account with no business-email requirement. The abstraction in `app/providers/base.py` is four methods; another vendor (Stannp, PostalMethods, …) is a new file, not a rewrite. |
| **Price** | $3.49 ($1.74 postage + $0.95 printing + $0.80 service) | **A placeholder.** PostGrid's Pay-Per-Piece rate for a US B&W first-class letter is roughly $1.02; check the current number and that it covers Stripe's fee before charging anyone. Set in `PRICE_*`. |
| **Cooldown** | 180 days per address, 3 letters lifetime | Deliberately conservative. This is the main lever between "a public service" and "a way to bother someone repeatedly". |
| **Retention** | 90 days, then erase | Long enough to answer "what did you send?" and settle a refund. |
| **No `react-router`** | A ~90-line hash router | Hash routing needs no server rewrites anywhere, and it removed the only routing dependency. If you later want history-API URLs, you will want the library back and a catch-all rewrite to `index.html`. |
| **Own signature verification** | Not the vendor SDKs | Keeps the code that decides "we were paid" short, readable and testable without the vendor package. The Stripe SDK is still used for API calls. |
| **Two-page maximum** | The template cannot exceed it | Pricing assumes it. Adding to the template risks a third page and a wrong price. |
| **Sender email required for mailing** | Yes | For the receipt and the mailing status. Not required for the free print-it-yourself path. |

### Things you must write before launch

The Privacy and Terms pages are accurate descriptions of what the code does, but
they carry visible `[ … ]` placeholders for details only you can supply: legal
entity name, business address, data-controller contact, governing law and venue,
and the refund window. They render as highlighted marks on the live page
specifically so they cannot ship unnoticed. They are in
`frontend/src/routes/Legal.tsx`.

**Have a lawyer read the Terms before you take money.** I wrote them to describe
the software honestly; that is not the same as them being sound.

---

## 5. Known limitations

- **US addresses only.** Stated on the address step and in the FAQ. Adding
  another country means a provider that mails there, address formats that are
  not `line1/city/state/zip`, and letter copy in another language.
- **No "delivered" status, ever.** First-class mail has no delivery
  confirmation. The furthest the receipt page goes is *processed for delivery*,
  which is what the postal service actually reports. This is a deliberate
  limitation, not a gap.
- **No account, so no history.** A sender who loses their receipt email has only
  the letter id. That is the cost of collecting almost nothing.
- **The retry and retention jobs need a scheduler.** Two one-line commands are
  in the deployment guide; nothing runs them automatically.
- **The suppression endpoint is unauthenticated.** Anyone can suppress any
  address. The worst outcome is that a letter is *not* sent, which is the
  direction to err in — but it does mean someone could pre-emptively suppress
  their own address, which is arguably a feature.
- **Rate limiting is per-IP.** Shared IPs share a limit; a determined person with
  many IPs is not stopped by it. The cooldown and the lifetime cap are the real
  protection.

---

## 6. If you only do three things

1. **Deploy the demo.** Import the repo at [vercel.com/new](https://vercel.com/new),
   set `VITE_API_BASE_URL=/`, deploy. It works today and needs no accounts.
2. **Add Neon and run `POST /api/v1/internal/migrate`** once you want the API to
   store anything.
3. **Before charging anyone**, check the price against PostGrid's current rates
   and send yourself a test letter end to end, with a test key, at your own
   address.
