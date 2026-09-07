#!/usr/bin/env node
/**
 * Regenerates `scripts/parity-expected.json` from the TypeScript composer.
 *
 * The TypeScript implementation is the reference, because it is the one the
 * sender's browser runs and therefore the one that produced the preview they
 * approved. The Python test suite asserts against this file; if the two
 * implementations drift, `backend/tests/test_parity.py` fails.
 *
 *   node scripts/gen-parity.mjs           # write the file
 *   node scripts/gen-parity.mjs --check   # fail if it is stale
 *
 * Bundles with esbuild — the copy in `frontend/node_modules` after `npm
 * install`, or the one inside a global `tsx` when the registry is unreachable.
 */
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const frontend = join(root, 'frontend');

function findEsbuild() {
  const candidates = [
    join(frontend, 'node_modules', '@esbuild', 'linux-x64', 'bin', 'esbuild'),
    join(frontend, 'node_modules', 'esbuild', 'bin', 'esbuild'),
  ];
  try {
    const globalRoot = execFileSync('npm', ['root', '-g'], { encoding: 'utf8' }).trim();
    candidates.push(
      join(globalRoot, 'tsx', 'node_modules', '@esbuild', 'linux-x64', 'bin', 'esbuild'),
      join(globalRoot, 'esbuild', 'bin', 'esbuild'),
    );
  } catch {
    /* npm not on PATH; the frontend candidates may still work */
  }
  return candidates.find(existsSync);
}

const esbuild = findEsbuild();
if (!esbuild) {
  console.error('esbuild not found. Run `npm install` in frontend/ first.');
  process.exit(2);
}

const tmp = mkdtempSync(join(tmpdir(), 'parity-'));
const entry = join(tmp, 'entry.ts');
writeFileSync(
  entry,
  `import { composeLetter, letterFingerprint } from ${JSON.stringify(join(frontend, 'src/lib/letter.ts'))};
import inputs from ${JSON.stringify(join(root, 'scripts/parity-inputs.json'))};
const out = (inputs as any[]).map((i) => {
  const doc = composeLetter({
    address: i.address,
    observations: i.observations,
    note: i.note,
    suggestions: i.suggestions,
    dateIso: i.dateIso,
  });
  return {
    name: i.name,
    plainText: doc.plainText,
    fingerprint: letterFingerprint(doc.plainText),
    contentVersion: doc.contentVersion,
    recipientLines: doc.recipientLines,
    blockKinds: doc.blocks.map((b) => b.kind),
  };
});
console.log(JSON.stringify(out, null, 2));
`,
  'utf8',
);

const bundle = join(tmp, 'bundle.mjs');
execFileSync(esbuild, [entry, '--bundle', '--format=esm', '--platform=node', '--loader:.json=json', `--outfile=${bundle}`], {
  stdio: ['ignore', 'ignore', 'inherit'],
});

const generated = execFileSync(process.execPath, [bundle], { encoding: 'utf8' }).trim() + '\n';
rmSync(tmp, { recursive: true, force: true });

const target = join(root, 'scripts', 'parity-expected.json');
if (process.argv.includes('--check')) {
  const current = existsSync(target) ? readFileSync(target, 'utf8') : '';
  if (current !== generated) {
    console.error('parity-expected.json is stale. Run: node scripts/gen-parity.mjs');
    process.exit(1);
  }
  console.log('parity fixtures are current');
} else {
  writeFileSync(target, generated, 'utf8');
  console.log(`wrote ${target}`);
}
// Keep the import helper referenced so linters do not flag it.
void pathToFileURL;
