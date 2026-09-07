#!/usr/bin/env node
/**
 * Copies shared/letter_content.json into the frontend and backend trees.
 *
 * Both copies are committed so neither project needs a build step or a path
 * alias that reaches outside its own root (which Vite and Docker both dislike).
 * The copies are checked byte-for-byte by tests on each side and by CI, so a
 * forgotten sync fails loudly instead of silently shipping two different
 * letters.
 *
 *   node scripts/sync-content.mjs          # write the copies
 *   node scripts/sync-content.mjs --check  # exit 1 if they are stale
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const source = join(root, 'shared', 'letter_content.json');
const targets = [
  join(root, 'frontend', 'src', 'content', 'letter_content.json'),
  join(root, 'backend', 'app', 'letters', 'letter_content.json'),
];

const check = process.argv.includes('--check');
const contents = readFileSync(source, 'utf8');

// Fail early on malformed JSON rather than shipping it.
JSON.parse(contents);

let stale = 0;
for (const target of targets) {
  let current = null;
  try {
    current = readFileSync(target, 'utf8');
  } catch {
    current = null;
  }
  if (current === contents) continue;
  if (check) {
    stale += 1;
    console.error(`stale: ${target}`);
  } else {
    writeFileSync(target, contents, 'utf8');
    console.log(`wrote: ${target}`);
  }
}

if (check) {
  if (stale > 0) {
    console.error(`\n${stale} copy/copies out of date. Run: node scripts/sync-content.mjs`);
    process.exit(1);
  }
  console.log('letter content is in sync');
} else if (!targets.length) {
  console.log('nothing to do');
}
