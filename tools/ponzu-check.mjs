#!/usr/bin/env node
/** Renders the Ponzu silhouette large, in every tone, for eyeballing. */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const globalRoot = execFileSync('npm', ['root', '-g'], { encoding: 'utf8' }).trim();
const pw = await import(pathToFileURL(join(globalRoot, 'playwright', 'index.js')).href);
const chromium = pw.chromium ?? pw.default.chromium;

const src = readFileSync(join(root, 'frontend/src/components/Ponzu.tsx'), 'utf8');
const pathMatch = src.match(/const BODY_PATH = \[([\s\S]*?)\]\.join\(' '\);/);
const bodyPath = pathMatch[1]
  .split('\n')
  .map((l) => l.trim().replace(/^'|',?$/g, ''))
  .filter(Boolean)
  .join(' ');

const tones = [
  { name: 'gold', body: '#e9c46a', collar: 'rgba(11,16,32,0.30)', accent: '#f2d894', eye: '#0b1020', bg: '#0b1020' },
  { name: 'clay', body: '#cf7256', collar: 'rgba(11,16,32,0.26)', accent: '#e9c46a', eye: '#2a1410', bg: '#0b1020' },
  { name: 'ink', body: '#3a352d', collar: 'rgba(253,250,244,0.5)', accent: '#8d4433', eye: '#fdfaf4', bg: '#fdfaf4' },
];

const svg = (t, w) => `<svg viewBox="0 0 250 150" width="${w}" xmlns="http://www.w3.org/2000/svg">
<defs><clipPath id="c-${t.name}"><path d="${bodyPath}"/></clipPath></defs>
<g fill="${t.body}">
<path d="M74 98h11v33a5.5 5.5 0 0 1-11 0z" opacity="0.45"/>
<path d="M143 96h11v34a5.5 5.5 0 0 1-11 0z" opacity="0.45"/>
<path d="M53 78c-9-2-14-7-12-12 5-1 10 4 14 9z"/>
<path d="M155 55C156 42 164 37 171 43L176 57Z"/>
<path d="M179 57C181 45 189 41 196 47L200 61Z"/>
<path d="${bodyPath}"/>
<path d="M92 100h11v32a5.5 5.5 0 0 1-11 0z"/>
<path d="M162 98h11v33a5.5 5.5 0 0 1-11 0z"/>
</g>
<g clip-path="url(#c-${t.name})"><path d="M146 30l17-2 22 84-17 3z" fill="${t.collar}"/></g>
<circle cx="197" cy="63" r="3.2" fill="${t.eye}" opacity="0.75"/>
<ellipse cx="222" cy="74" rx="4.6" ry="5.4" fill="${t.eye}" opacity="0.28"/>
<path d="M40 26l3.8 9.6L53 39l-9.2 3.4L40 52l-3.8-9.6L27 39l9.2-3.4z" fill="${t.accent}"/>
</svg>`;

const html = `<body style="margin:0;font-family:system-ui">
${tones
  .map(
    (t) =>
      `<div style="background:${t.bg};padding:24px;display:flex;gap:32px;align-items:center">${svg(t, 620)}${svg(t, 150)}${svg(t, 92)}</div>`,
  )
  .join('')}
</body>`;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 960, height: 1300 }, deviceScaleFactor: 2 });
await page.setContent(html);
await page.screenshot({ path: join(root, '.shots', 'ponzu.png'), fullPage: true });
await browser.close();
console.log('wrote .shots/ponzu.png');
