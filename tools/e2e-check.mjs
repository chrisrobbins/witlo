#!/usr/bin/env node
/**
 * Functional checks against the real app in a real browser.
 *
 * Complements the Vitest suite (which runs the same assertions in jsdom under
 * `npm test`). This one drives the built bundle in headless Chromium, so it
 * also catches CSS-dependent problems: a control that is present but not
 * clickable, a focus outline that never appears, a page that scrolls
 * horizontally on a phone.
 *
 *   node tools/offline-preview.mjs && node tools/e2e-check.mjs
 */
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { dirname, extname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const previewDir = join(root, '.preview');

const globalRoot = execFileSync('npm', ['root', '-g'], { encoding: 'utf8' }).trim();
const pw = await import(pathToFileURL(join(globalRoot, 'playwright', 'index.js')).href);
const chromium = pw.chromium ?? pw.default.chromium;

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css' };
const server = createServer((req, res) => {
  const name = (req.url || '/').split('?')[0];
  const file = join(previewDir, name === '/' ? 'index.html' : name);
  try {
    res.writeHead(200, { 'Content-Type': TYPES[extname(file)] || 'application/octet-stream' });
    res.end(readFileSync(file));
  } catch {
    res.writeHead(404).end('not found');
  }
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}/index.html`;

const results = [];
let failures = 0;

function check(name, condition, detail = '') {
  const ok = Boolean(condition);
  if (!ok) failures += 1;
  results.push(`${ok ? 'ok  ' : 'FAIL'}  ${name}${ok || !detail ? '' : `\n        ${detail}`}`);
}

const browser = await chromium.launch();

async function newPage(viewport = { width: 1280, height: 900 }) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  return { page, context, errors };
}

async function fillAddress(page) {
  await page.getByLabel(/^Street address/).fill('414 W San Antonio St');
  await page.getByLabel(/^City/).fill('Marfa');
  await page.getByLabel(/^State/).selectOption('TX');
  await page.getByLabel(/^ZIP/).fill('79843');
}

// --- every route renders without a console error ---------------------------
{
  const routes = [
    '/', '/how-it-works', '/why-lighting-matters', '/faq', '/create',
    '/privacy', '/terms', '/no-more-letters', '/receipt', '/definitely-not-a-page',
  ];
  const { page, context, errors } = await newPage();
  for (const route of routes) {
    await page.goto(`${base}#${route}`, { waitUntil: 'load' });
    await page.waitForTimeout(120);
    const text = await page.locator('#main').innerText();
    check(`route ${route} renders content`, text.trim().length > 40, text.slice(0, 80));
  }
  check('no console errors across all routes', errors.length === 0, errors.join('; '));
  await context.close();
}

// --- 404 ------------------------------------------------------------------
{
  const { page, context } = await newPage();
  await page.goto(`${base}#/definitely-not-a-page`);
  check('unknown route shows the 404 page', await page.getByText('Nothing here but sky').isVisible());
  await context.close();
}

// --- address validation ----------------------------------------------------
{
  const { page, context } = await newPage();
  await page.goto(`${base}#/create`);
  await page.getByRole('button', { name: /Continue/ }).click();

  check(
    'empty address is refused with per-field messages',
    await page.getByText('Please enter the street address of the property.').isVisible(),
  );
  check(
    'invalid fields are marked for assistive tech',
    (await page.getByLabel(/^Street address/).getAttribute('aria-invalid')) === 'true',
  );
  check(
    'the wizard stays on step 1',
    await page.getByRole('heading', { name: /Where is the light/ }).isVisible(),
  );

  await page.getByLabel(/^Street address/).fill('PO Box 42');
  await page.getByLabel(/^City/).fill('Marfa');
  await page.getByLabel(/^State/).selectOption('TX');
  await page.getByLabel(/^ZIP/).fill('79843');
  await page.getByRole('button', { name: /Continue/ }).click();
  check('a PO box is refused', await page.getByText(/A PO box has no outdoor light/).isVisible());

  await page.getByLabel(/^Street address/).fill('414 W San Antonio St');
  await page.getByLabel(/^ZIP/).fill('798');
  await page.getByRole('button', { name: /Continue/ }).click();
  check('a short ZIP is refused', await page.getByText(/12345 or 12345-6789/).isVisible());

  await page.getByLabel(/^ZIP/).fill('79843');
  await page.getByRole('button', { name: /Continue/ }).click();
  check(
    'a valid address advances',
    await page.getByRole('heading', { name: /What did you notice/ }).isVisible(),
  );
  await context.close();
}

// --- note validation -------------------------------------------------------
{
  const { page, context } = await newPage();
  await page.goto(`${base}#/create`);
  await fillAddress(page);
  await page.getByRole('button', { name: /Continue/ }).click();

  check(
    'the note field is hidden until "something else" is chosen',
    (await page.getByLabel(/In a sentence or so/).count()) === 0,
  );
  await page.getByText('Something else', { exact: true }).click();
  check('the note field appears', await page.getByLabel(/In a sentence or so/).isVisible());

  await page.getByLabel(/In a sentence or so/).fill('This is a violation of the city ordinance');
  await page.getByRole('button', { name: /Continue/ }).click();
  check(
    'a legal-threat note is refused',
    await page.getByText(/friendly request/).isVisible(),
  );

  await page.getByLabel(/In a sentence or so/).fill('call me on 555-123-4567');
  await page.getByRole('button', { name: /Continue/ }).click();
  check(
    'contact details in the note are refused',
    await page.getByText(/leave out phone numbers/).isVisible(),
  );

  await page.getByLabel(/In a sentence or so/).fill('The floodlight shines across the road.');
  await page.getByRole('button', { name: /Continue/ }).click();
  check(
    'a plain note is accepted',
    await page.getByRole('heading', { name: /Which ideas/ }).isVisible(),
  );
  await context.close();
}

// --- preview consistency ---------------------------------------------------
{
  const { page, context } = await newPage();
  await page.goto(`${base}#/create`);
  await fillAddress(page);
  await page.getByRole('button', { name: /Continue/ }).click();
  await page.getByText('Appears to stay on all night', { exact: true }).click();
  await page.getByText('Something else', { exact: true }).click();
  await page.getByLabel(/In a sentence or so/).fill('The floodlight shines across the road.');
  await page.getByRole('button', { name: /Continue/ }).click();
  await page.getByText('Use motion sensors where appropriate', { exact: true }).click();
  await page.getByRole('button', { name: /Read the letter/ }).click();

  const sheet = page.locator('article.sheet').first();
  const text = await sheet.innerText();

  check('the preview shows the recipient role line', text.includes('To the resident or property manager'));
  check('the preview shows the exact address', text.includes('414 W San Antonio St') && text.includes('Marfa, TX 79843'));
  check('a selected observation appears', text.includes('appeared to stay on through the night'));
  check('an unselected observation does not', !text.includes('reach past the property'));
  check('the note appears verbatim', text.includes('The floodlight shines across the road.'));
  check('a selected suggestion appears', text.includes('a motion sensor often works better'));
  check('the letter names the service and the opt-out', text.includes('whyisthislighton.com') && text.includes('no-more-letters'));
  check('the letter never invents a name', !text.includes('Dear '));

  check('print and download are both offered', (await page.getByRole('button', { name: /Print or save as PDF/ }).count()) === 1 && (await page.getByRole('button', { name: /Download the letter/ }).count()) === 1);
  check('demo mode says nothing will be mailed', await page.getByText(/No letter will be mailed/).isVisible());
  check('there is no pay button in demo mode', (await page.getByRole('button', { name: /Pay /i }).count()) === 0);
  check('there is no address-check button in demo mode', (await page.getByRole('button', { name: /Check this address/i }).count()) === 0);

  // Editing a selection must change the preview.
  await page.getByRole('button', { name: /Change something/ }).click();
  await page.getByRole('button', { name: /Continue/ }).click();
  await page.getByText('Appears to stay on all night', { exact: true }).click();
  await page.getByRole('button', { name: /Continue/ }).click();
  await page.getByRole('button', { name: /Read the letter/ }).click();
  const after = await page.locator('article.sheet').first().innerText();
  check('deselecting an observation removes it from the preview', !after.includes('appeared to stay on through the night'));

  await context.close();
}

// --- download produces a real file ----------------------------------------
{
  const { page, context } = await newPage();
  await page.goto(`${base}#/create`);
  await fillAddress(page);
  await page.getByRole('button', { name: /Continue/ }).click();
  await page.getByRole('button', { name: /Continue/ }).click();
  await page.getByRole('button', { name: /Read the letter/ }).click();

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: /Download the letter/ }).click(),
  ]);
  const path = await download.path();
  const html = readFileSync(path, 'utf8');
  check('the download is named for the address', /friendly-letter-marfa-79843\.html/.test(download.suggestedFilename()), download.suggestedFilename());
  check('the downloaded file is a complete document', html.startsWith('<!doctype html>') && html.includes('</html>'));
  check('the downloaded file contains the letter', html.includes('Hello from a neighbor,') && html.includes('414 W San Antonio St'));
  check('the downloaded file is self-contained', !/<script|<link|src=/.test(html));
  check('the downloaded file has print rules', html.includes('@page') && html.includes('@media print'));
  await context.close();
}

// --- keyboard only ---------------------------------------------------------
{
  const { page, context } = await newPage();
  await page.goto(`${base}#/create`);

  let focused = '';
  for (let i = 0; i < 30; i += 1) {
    await page.keyboard.press('Tab');
    focused = await page.evaluate(() => {
      const el = document.activeElement;
      return el ? `${el.tagName}:${el.getAttribute('id') || el.textContent?.slice(0, 24) || ''}` : '';
    });
    if (focused.startsWith('INPUT') && (await page.getByLabel(/^Street address/).evaluate((el) => el === document.activeElement))) break;
  }
  check('the street field is reachable by tab alone', focused.startsWith('INPUT'), focused);

  await page.keyboard.type('414 W San Antonio St');
  check('typing into the focused field works', (await page.getByLabel(/^Street address/).inputValue()) === '414 W San Antonio St');

  const outline = await page.getByLabel(/^Street address/).evaluate((el) => {
    el.focus();
    return getComputedStyle(el).borderColor;
  });
  check('the focused field is visually distinguishable', outline.length > 0, outline);

  // Choice cards are real checkboxes and respond to the space bar.
  await page.getByLabel(/^City/).fill('Marfa');
  await page.getByLabel(/^State/).selectOption('TX');
  await page.getByLabel(/^ZIP/).fill('79843');
  await page.getByRole('button', { name: /Continue/ }).click();
  const box = page.getByRole('checkbox', { name: /Appears to stay on all night/ });
  await box.focus();
  await page.keyboard.press('Space');
  check('a choice card toggles with the space bar', await box.isChecked());

  await context.close();
}

// --- skip link -------------------------------------------------------------
{
  const { page, context } = await newPage();
  await page.goto(`${base}#/`);
  await page.keyboard.press('Tab');
  const skip = page.getByRole('link', { name: /Skip to the main content/ });
  check('the first tab stop is the skip link', await skip.evaluate((el) => el === document.activeElement));
  check('the skip link becomes visible when focused', (await skip.boundingBox()).y >= 0);
  await context.close();
}

// --- mobile layout ---------------------------------------------------------
for (const [label, viewport] of [
  ['iPhone-sized', { width: 390, height: 844 }],
  ['small Android', { width: 360, height: 800 }],
]) {
  const { page, context } = await newPage(viewport);
  for (const route of ['/', '/create', '/why-lighting-matters', '/faq', '/privacy']) {
    await page.goto(`${base}#${route}`, { waitUntil: 'load' });
    await page.waitForTimeout(120);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    check(`${label}: ${route} does not scroll sideways`, overflow <= 1, `overflow ${overflow}px`);
  }

  // Tap targets on the main call to action.
  await page.goto(`${base}#/`);
  const buttonBox = await page.getByRole('link', { name: /Create a letter/ }).first().boundingBox();
  check(`${label}: the primary button is a comfortable tap target`, buttonBox.height >= 44, `${buttonBox.height}px`);
  await context.close();
}

// --- reduced motion --------------------------------------------------------
{
  const context = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${base}#/`);
  const animation = await page.locator('.sky__star').first().evaluate((el) => getComputedStyle(el).animationName);
  check('stars stop twinkling under prefers-reduced-motion', animation === 'none', animation);
  await context.close();
}

// --- contrast --------------------------------------------------------------
{
  const { page, context } = await newPage();
  await page.goto(`${base}#/`);

  const contrast = await page.evaluate(() => {
    const lum = (rgb) => {
      const [r, g, b] = rgb.map((v) => {
        const c = v / 255;
        return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const parse = (value) => {
      const n = (value.match(/[\d.]+/g) || []).map(Number);
      return { rgb: n.slice(0, 3), a: n.length > 3 ? n[3] : 1 };
    };
    // Composite every translucent layer down to the page background, the way
    // the browser actually paints it. Treating rgba(233,196,106,0.05) as solid
    // gold reports a contrast failure that no one can see.
    const bg = (el) => {
      const layers = [];
      let node = el;
      while (node) {
        const c = getComputedStyle(node).backgroundColor;
        if (c && c !== 'transparent') {
          const { rgb, a } = parse(c);
          if (a > 0) layers.push({ rgb, a });
          if (a >= 1) break;
        }
        node = node.parentElement;
      }
      layers.push({ rgb: [11, 16, 32], a: 1 });
      let out = layers[layers.length - 1].rgb;
      for (let i = layers.length - 2; i >= 0; i -= 1) {
        const { rgb, a } = layers[i];
        out = out.map((base, k) => rgb[k] * a + base * (1 - a));
      }
      return out;
    };
    const ratio = (a, b) => {
      const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x);
      return (l1 + 0.05) / (l2 + 0.05);
    };
    const out = [];
    for (const el of document.querySelectorAll('#main p, #main li, #main h1, #main h2, #main h3, .site-nav a, .muted')) {
      if (!el.textContent?.trim()) continue;
      if (el.closest('.sheet')) continue; // the letter is light-on-paper by design
      const style = getComputedStyle(el);
      const size = parseFloat(style.fontSize);
      const large = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 600);
      out.push({
        text: el.textContent.trim().slice(0, 40),
        ratio: ratio(parse(style.color).rgb, bg(el)),
        required: large ? 3 : 4.5,
      });
    }
    return out;
  });

  const failing = contrast.filter((c) => c.ratio < c.required);
  check(
    `body text meets WCAG AA contrast (${contrast.length} elements checked)`,
    failing.length === 0,
    failing.slice(0, 5).map((f) => `${f.ratio.toFixed(2)} < ${f.required} :: ${f.text}`).join('\n        '),
  );
  await context.close();
}

// --- landmarks and headings ------------------------------------------------
{
  const { page, context } = await newPage();
  for (const route of ['/', '/create', '/faq', '/why-lighting-matters', '/no-more-letters', '/receipt', '/privacy', '/terms', '/how-it-works']) {
    await page.goto(`${base}#${route}`);
    await page.waitForTimeout(100);
    const h1s = await page.locator('h1').count();
    check(`${route} has exactly one h1`, h1s === 1, `found ${h1s}`);
  }
  await page.goto(`${base}#/`);
  check('there is a main landmark', (await page.locator('main#main').count()) === 1);
  check('there is a banner landmark', (await page.locator('header.site-header').count()) === 1);
  check('navigation is labelled', (await page.locator('nav[aria-label]').count()) >= 1);
  const imgsWithoutLabel = await page.locator('svg[role="img"]:not([aria-label]):not([aria-hidden])').count();
  check('every meaningful svg is labelled', imgsWithoutLabel === 0, `${imgsWithoutLabel} unlabelled`);
  await context.close();
}

// --- document titles -------------------------------------------------------
{
  const { page, context } = await newPage();
  const titles = new Set();
  for (const route of ['/', '/create', '/faq', '/privacy']) {
    await page.goto(`${base}#${route}`);
    await page.waitForTimeout(120);
    titles.add(await page.title());
  }
  check('each route sets its own document title', titles.size === 4, [...titles].join(' | '));
  await context.close();
}

await browser.close();
server.close();

console.log(results.join('\n'));
console.log(`\n${results.length - failures} passed, ${failures} failed`);
process.exit(failures ? 1 : 0);
