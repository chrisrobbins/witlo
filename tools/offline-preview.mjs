#!/usr/bin/env node
/**
 * Offline preview builder — a fallback, not the real build.
 *
 * `npm run build` in frontend/ (Vite) is the supported path and the one CI and
 * GitHub Pages use. This script exists for environments that cannot reach the
 * npm registry: it bundles the same sources with the esbuild binary that ships
 * inside `tsx`, resolving react/react-dom from a global install. The output is
 * good enough to open in a browser and check layout, contrast, keyboard order
 * and print styles, which is what it is for.
 *
 *   node tools/offline-preview.mjs [--outdir .preview] [--api-base ""]
 */
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync, symlinkSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const frontend = join(root, 'frontend');

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i > -1 && process.argv[i + 1] !== undefined ? process.argv[i + 1] : fallback;
}

const outdir = resolve(root, arg('--outdir', '.preview'));
const apiBase = arg('--api-base', '');

// --- locate esbuild + react without a package install ------------------------
const globalRoot = execFileSync('npm', ['root', '-g'], { encoding: 'utf8' }).trim();
const esbuildBin = join(globalRoot, 'tsx', 'node_modules', '@esbuild', 'linux-x64', 'bin', 'esbuild');
const esbuild = existsSync(esbuildBin)
  ? esbuildBin
  : join(globalRoot, 'esbuild', 'bin', 'esbuild');

if (!existsSync(esbuild)) {
  console.error('No esbuild binary found. Use the real Vite build instead: cd frontend && npm run build');
  process.exit(2);
}

const localModules = join(frontend, 'node_modules');
mkdirSync(localModules, { recursive: true });
for (const pkg of ['react', 'react-dom', 'scheduler']) {
  const link = join(localModules, pkg);
  const target = join(globalRoot, pkg);
  if (!existsSync(link) && existsSync(target)) symlinkSync(target, link, 'dir');
}

rmSync(outdir, { recursive: true, force: true });
mkdirSync(outdir, { recursive: true });

const env = JSON.stringify({
  BASE_URL: './',
  MODE: 'production',
  DEV: false,
  PROD: true,
  VITE_API_BASE_URL: apiBase,
  VITE_CONTACT_EMAIL: 'hello@whyisthislighton.com',
});

execFileSync(
  esbuild,
  [
    join(frontend, 'src', 'main.tsx'),
    '--bundle',
    '--format=esm',
    '--target=es2020',
    '--loader:.json=json',
    `--define:import.meta.env=${env}`,
    '--define:process.env.NODE_ENV="production"',
    `--outfile=${join(outdir, 'app.js')}`,
  ],
  { stdio: 'inherit', cwd: frontend },
);

const html = readFileSync(join(frontend, 'index.html'), 'utf8')
  .replace('<script type="module" src="/src/main.tsx"></script>', '<script type="module" src="./app.js"></script>')
  .replace('</head>', '  <link rel="stylesheet" href="./app.css">\n  </head>');

writeFileSync(join(outdir, 'index.html'), html, 'utf8');
console.log(`\npreview written to ${outdir}/index.html`);
