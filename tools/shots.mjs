#!/usr/bin/env node
/**
 * Drives the offline preview in headless Chromium and writes screenshots.
 * Used during development to check layout, contrast and print output at real
 * viewport sizes. Not part of the app build.
 *
 *   node tools/shots.mjs [outdir]
 */
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdirSync, readFileSync } from 'node:fs';
import { dirname, extname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const globalRoot = execFileSync('npm', ['root', '-g'], { encoding: 'utf8' }).trim();
const pw = await import(pathToFileURL(join(globalRoot, 'playwright', 'index.js')).href);
const chromium = pw.chromium ?? pw.default.chromium;

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const previewDir = join(root, '.preview');

// ES modules cannot load over file://, so serve the preview on localhost.
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.map': 'application/json' };
const server = createServer((req, res) => {
  const name = (req.url || '/').split('?')[0];
  const file = join(previewDir, name === '/' ? 'index.html' : name);
  try {
    const body = readFileSync(file);
    res.writeHead(200, { 'Content-Type': TYPES[extname(file)] || 'application/octet-stream' });
    res.end(body);
  } catch {
    res.writeHead(404).end('not found');
  }
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const preview = `http://127.0.0.1:${server.address().port}/index.html`;
const out = process.argv[2] ? join(root, process.argv[2]) : join(root, '.shots');
mkdirSync(out, { recursive: true });

const DESKTOP = { width: 1440, height: 960 };
const MOBILE = { width: 390, height: 844 };

const browser = await chromium.launch();
const errors = [];

async function shot(name, viewport, path, prepare) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(`[${name}] console: ${m.text()}`);
  });
  page.on('pageerror', (e) => errors.push(`[${name}] pageerror: ${e.message}`));
  await page.goto(`${preview}#${path}`, { waitUntil: 'load' });
  await page.waitForTimeout(250);
  if (prepare) await prepare(page);
  await page.waitForTimeout(200);
  await page.screenshot({ path: join(out, `${name}.png`), fullPage: true });
  await ctx.close();
}

const fill = async (page) => {
  await page.getByLabel('Street address').fill('414 W San Antonio St');
  await page.getByLabel('City').fill('Marfa');
  await page.getByLabel('State', { exact: false }).selectOption('TX');
  await page.getByLabel('ZIP').fill('79843');
};

await shot('desktop-home', DESKTOP, '/');
await shot('mobile-home', MOBILE, '/');
await shot('desktop-how', DESKTOP, '/how-it-works');
await shot('desktop-learn', DESKTOP, '/why-lighting-matters');
await shot('desktop-faq', DESKTOP, '/faq');
await shot('desktop-create-1', DESKTOP, '/create');
await shot('mobile-create-1', MOBILE, '/create');
await shot('desktop-create-2', DESKTOP, '/create', async (page) => {
  await fill(page);
  await page.getByRole('button', { name: /Continue/ }).click();
});
await shot('desktop-create-3', DESKTOP, '/create', async (page) => {
  await fill(page);
  await page.getByRole('button', { name: /Continue/ }).click();
  await page.getByText('Appears to stay on all night').click();
  await page.getByRole('button', { name: /Continue/ }).click();
});
await shot('desktop-create-4', DESKTOP, '/create', async (page) => {
  await fill(page);
  await page.getByRole('button', { name: /Continue/ }).click();
  await page.getByText('Appears to stay on all night').click();
  await page.getByText('Shines upward').click();
  await page.getByRole('button', { name: /Continue/ }).click();
  await page.getByRole('button', { name: /Read the letter/ }).click();
});
await shot('mobile-create-4', MOBILE, '/create', async (page) => {
  await fill(page);
  await page.getByRole('button', { name: /Continue/ }).click();
  await page.getByRole('button', { name: /Continue/ }).click();
  await page.getByRole('button', { name: /Read the letter/ }).click();
});
await shot('desktop-privacy', DESKTOP, '/privacy');
await shot('desktop-nomore', DESKTOP, '/no-more-letters');
await shot('desktop-404', DESKTOP, '/nope');

// print view
{
  const ctx = await browser.newContext({ viewport: DESKTOP });
  const page = await ctx.newPage();
  await page.goto(`${preview}#/create`, { waitUntil: 'load' });
  await fill(page);
  await page.getByRole('button', { name: /Continue/ }).click();
  // worst case: every observation, a full-length note, every suggestion
  for (const label of ['Appears to stay on all night', 'Shines upward', 'Spills beyond the property', 'Lights an area that appears unused', 'Something else']) {
    await page.getByText(label, { exact: true }).click();
  }
  await page.getByLabel('In a sentence or so').fill('The floodlight above the side door shines across the road and into the arroyo behind our house, and it is aimed slightly upward.');
  await page.getByRole('button', { name: /Continue/ }).click();
  for (const label of ['Turn off lights when they are not needed', 'Use a timer', 'Use motion sensors where appropriate', 'Shield or aim fixtures downward', 'Use lower brightness', 'Consider warmer light']) {
    const box = page.getByText(label, { exact: true });
    if (!(await box.count())) continue;
    const input = box.locator('xpath=ancestor::label').locator('input');
    if (!(await input.isChecked())) await box.click();
  }
  await page.getByRole('button', { name: /Read the letter/ }).click();
  await page.emulateMedia({ media: 'print' });
  await page.pdf({ path: join(out, 'letter-print.pdf'), format: 'Letter', printBackground: true });
  await page.screenshot({ path: join(out, 'print-view.png'), fullPage: true });
  await ctx.close();
}

await browser.close();
server.close();

if (errors.length) {
  console.error('\nBrowser problems:\n' + errors.join('\n'));
  process.exit(1);
}
console.log(`screenshots in ${out}`);
