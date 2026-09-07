# Design notes

The brief was a West Texas night sky: deep midnight blue, warm cream, muted
terracotta, restrained gold — sophisticated enough for adults, welcoming enough
for a family, and never a dashboard.

## The palette, and why it passes

Tokens live in `frontend/src/styles/tokens.css`. The contrast ratios below are
against `--night-800` (`#0b1020`), the page background, and are measured by
`tools/e2e-check.mjs` in a real browser with translucent layers composited the
way the browser paints them — a check that catches the mistakes a static
calculator misses.

| Token | Value | On `--night-800` | Used for |
|---|---|---|---|
| `--cream-200` | `#eadfcc` | 14.8:1 | body text |
| `--cream-50` | `#fefaf3` | 17.6:1 | headings |
| `--cream-400` | `#a1957f` | 6.2:1 | muted text — still AA at body size |
| `--gold-400` | `#e9c46a` | 10.2:1 | links, accents, the primary button's fill |
| `--clay-400` | `#cf7256` | 5.0:1 | warm accents, the letter's bullet marks |
| `--stop-400` | `#e58a72` | 6.6:1 | validation messages |

Gold is used as an accent and as the primary button's *background* (with
near-black text), never as a large field of colour. A page of gold would read as
a warning, not a night sky.

The letter sheet is the deliberate exception: it is always paper — light
background, dark ink, its own `color-scheme` — because it must look identical on
screen and on the page that comes out of a printer.

## Type

No web fonts. Two reasons: a self-hosted or CDN font is one more thing that can
fail to load on a Pages deploy, and a Google Fonts request is a third-party
request on a site whose privacy page promises there are none.

- **Display** — `Iowan Old Style`, `Palatino`, `Book Antiqua`, Georgia. A warm
  old-style serif on most machines, a decent serif everywhere else.
- **Body** — the system UI stack. It renders at the size the reader chose.
- **The letter** — the same old-style serif, at 11.5pt on screen and 10.4pt in
  print, because a letter should look like a letter.

The scale is fluid (`clamp()` between a mobile and a desktop size) so nothing
needs a breakpoint to stay proportionate.

## Motion

There is exactly one animation: stars that fade slowly, on a 6-second cycle with
staggered delays. It is CSS-only, and `prefers-reduced-motion: reduce` disables
it along with smooth scrolling and every transition. The browser check asserts
that the star animation resolves to `none` under that preference — a claim that
is easy to make and easy to break.

The star field is generated from a fixed seed, so the sky is identical on every
render and every reload. A sky that reshuffles as you navigate is distracting,
and a deterministic one also makes screenshot comparison possible.

## Ponzu

An original javelina, drawn as a single SVG path plus a clipped collar band:
body, bristled mane and wedge-shaped head flowing together with no neck, which is
what makes a javelina read as a javelina rather than a pig. Small rounded ears,
a pale collar, a long snout, four thin legs with the far pair dimmed.

He is a silhouette rather than a cartoon on purpose. A woodcut or postal-stamp
treatment can sit at the bottom of a letter about light pollution without
undermining the letter; a cartoon cannot. He appears in four tones — the `ink`
one is what prints — and reads correctly down to 92px, which is the size on the
letter itself.

## Layout

- One content column, `66ch` maximum for prose. Long lines are where credibility
  goes to die.
- The wizard is two columns on desktop — the step on the left, a live scaled-down
  preview on the right — and collapses to one column on narrow screens with the
  preview moved above the form, so a phone user sees what they are building
  before they scroll.
- The final step drops the sidebar entirely and gives the full width to the
  letter, capped at 52.5rem so the sheet lines up with the heading above it.
- Everything is `clamp()` and `auto-fit` grids; there are four breakpoints in the
  whole stylesheet.

## Print

`print.css` removes the site and leaves the letter: no navigation, no buttons,
no demo banner, no dark background. `@page { size: Letter portrait; margin:
0.7in }`, orphan and widow control on the body, and `break-inside: avoid` on the
sign-off and footer so a letter never splits across a page in an ugly place.

A typical letter — a few observations, a few suggestions — is one page. The
longest the template can produce is two, which is what the pricing assumes and
what `estimate_pages` is calibrated against.

The version the mailing provider prints
(`backend/app/letters/render.py`) is a separate, self-contained HTML document
that mirrors the same layout, with 2.5 inches reserved at the top of page one for
the envelope window.

## Small deliberate things

- The example letter on the home page is collapsed with a fade and a "Read the
  whole letter" button. Uncollapsed it made the landing page 8,000 pixels tall.
- Every letter preview shows a short fingerprint of its own text. It is a change
  detector the server also computes, and showing it makes the promise
  "this is exactly what will print" checkable rather than rhetorical.
- Validation messages are written to be read aloud without sounding like an error
  dialog: "That looks a little short for a street address", not "Invalid input".
- The `[ … ]` placeholders on the Privacy and Terms pages render as visible
  highlighted marks. A placeholder you cannot see is a placeholder that ships.
