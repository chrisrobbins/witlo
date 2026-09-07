# Why Is This Light On?

A small public service that helps a neighbor send a friendly, informative paper
letter to an address where an outdoor light may be on unnecessarily.

It is the constructive half of a story about Ponzu Benedicio, a young javelina in
Marfa, Texas, who tried smashing the lights first and learned why that hurt the
people around him.

**A better night starts with a friendly letter.**

---

## What this actually is

A static React site that anyone can use to write and print a letter for free, and
a separately hosted Python API that can print and post that letter for a
published price when — and only when — you have configured a mailing service.

The letter is assembled from a fixed, carefully written template. **No language
model is involved anywhere in this service.** The sender chooses which
observations and which suggestions appear; that is the entire range of what a
letter can say.

## Architecture

```
                     GitHub Pages (static)              Separately hosted
   ┌──────────────────────────────────┐        ┌────────────────────────────────┐
   │  React 19 + TypeScript + Vite    │        │  FastAPI + SQLAlchemy          │
   │                                  │        │  PostgreSQL                    │
   │  • hash routing — no rewrites    │        │                                │
   │  • composes the letter locally   │  HTTPS │  • composes the letter again   │
   │  • prints / downloads it         │ ─────► │  • validates the address       │
   │  • DEMO MODE by default          │  CORS  │  • prices it (server is the    │
   │                                  │        │    only authority on price)    │
   └──────────────────────────────────┘        │  • state machine + idempotency │
                                               └───────┬───────────────┬────────┘
                                                       │               │
                                            signed webhooks     signed webhooks
                                                       │               │
                                                ┌──────▼─────┐  ┌──────▼──────┐
                                                │   Stripe   │  │  Lob (print │
                                                │  Checkout  │  │  and post)  │
                                                └────────────┘  └─────────────┘
```

GitHub Pages serves static files and cannot run Python, which is why the API is
deployed elsewhere. The frontend reaches it through one environment variable and
nothing else.

### The three ideas worth knowing

**Demo mode is the default, and it is a real product, not a placeholder.** With
no `VITE_API_BASE_URL` set, the whole address-to-preview journey works in the
browser: you write the letter, read it, and print it or download a
self-contained HTML file you can post yourself. There is no code path from that
build to a network call that could mail or charge anything — every function in
`lib/api.ts` throws before it touches `fetch`, and a test asserts it.

**The letter is composed twice, identically.** `frontend/src/lib/letter.ts` and
`backend/app/letters/composer.py` are mirrors of each other, both reading the
same `shared/letter_content.json`. A shared fixture table proves they produce
byte-identical output, so the letter a sender approved in their browser is
provably the letter the printer receives. The server recomposes and compares
before it prints; a mismatch stops the letter.

**The browser is never the authority on money or mail.** A letter moves to
`paid` only from a signature-verified payment webhook. The success redirect a
browser lands on renders a status page and does nothing else. Three unique
constraints in the database — on webhook events, on idempotency keys, and on the
provider's letter id — make double-charging and double-mailing collisions rather
than judgement calls.

## Repository layout

```
frontend/          React + TypeScript + Vite. Publishable to GitHub Pages as-is.
  src/lib/         letter composition, address handling, validation, API client
  src/routes/      the pages and the four-step wizard
  src/styles/      design tokens, components, the letter sheet, print rules
  tests/           Vitest: composition, parity, demo safety, the wizard
backend/           FastAPI + SQLAlchemy + Alembic.
  app/letters/     composition, address normalization, print rendering
  app/providers/   mailing-provider abstraction (mock, Lob)
  app/payments/    payment-provider abstraction (mock, Stripe)
  app/services/    state machine, pricing, orchestration
  tests/           pytest: composition, signatures, the money-and-mail path
shared/            letter_content.json — the single source of every printed word
scripts/           content sync, TS↔Python parity fixtures
tools/             local verification helpers (see "Verifying it" below)
docs/              deployment guide, status report, design notes
```

## Quick start

### The demo, with nothing else installed

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

That is the complete free experience: write a letter, read it, print it.

### With the API

```bash
cp backend/.env.example backend/.env       # defaults are already demo-safe
docker compose up --build                  # PostgreSQL + the API on :8000
docker compose exec api alembic upgrade head
```

Then point the frontend at it:

```bash
echo 'VITE_API_BASE_URL=http://localhost:8000' > frontend/.env.local
cd frontend && npm run dev
```

Without Docker:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL="sqlite+pysqlite:///./wittl.db"   # no PostgreSQL needed
alembic upgrade head
uvicorn app.main:app --reload
```

The mock mailing provider recognises test addresses so you can exercise every
branch by hand — a ZIP of `00000` is undeliverable, a street line containing
`provider down` fails retryably, and so on. They are listed at the top of
`backend/app/providers/mock.py`.

## Running the tests

```bash
cd backend  && pytest                     # 100+ tests, all external services mocked
cd frontend && npm test                   # Vitest, including the wizard in jsdom
node scripts/sync-content.mjs --check     # the letter content has not drifted
node scripts/gen-parity.mjs --check       # TypeScript and Python still agree
```

Nothing in either suite can reach Stripe, Lob or the postal service.

### Verifying it in a browser

`tools/` holds two helpers used during development, both independent of the npm
registry:

```bash
node tools/offline-preview.mjs   # bundles the app with esbuild
node tools/e2e-check.mjs         # 75 checks in headless Chromium
node tools/shots.mjs             # screenshots at desktop and phone sizes
```

`e2e-check.mjs` drives the real UI: validation messages, note filtering, preview
consistency, the download, keyboard-only operation, tap-target sizes, horizontal
overflow at 360px, `prefers-reduced-motion`, WCAG AA contrast with translucent
backgrounds composited properly, one `<h1>` per page. These are a supplement to
the Vitest suite, not a replacement.

## Going live

Demo mode needs no credentials and no decisions. Live mailing needs both, and
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) walks through all of it: GitHub Pages,
custom-domain DNS, deploying the API, environment variables, and the switch from
demo to live.

[`docs/STATUS.md`](docs/STATUS.md) is the honest list — what works, what was
tested and how, and exactly what still needs your accounts or a business
decision.

## A note on the copy

The letter avoids shaming, accusation and anything resembling enforcement
language, and it never claims a light is unnecessary — only that it may be
contributing to nighttime brightness. A test asserts the absence of that
vocabulary, because it is the sort of thing that erodes one word at a time.

The educational claims are drawn from
[DarkSky International](https://darksky.org) and linked to their sources. Where
the evidence is genuinely mixed — the relationship between lighting and crime,
for instance — the site says so rather than picking the convenient side. This
project is not affiliated with or endorsed by DarkSky International.

## Licence

MIT. Ponzu Benedicio and the surrounding story are original characters.
