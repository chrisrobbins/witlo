/**
 * Builds a standalone, print-ready HTML file of the letter.
 *
 * Self-contained on purpose: someone who downloads this should be able to open
 * it on a machine with no network, print it, and put it in an envelope
 * themselves. That is the free path through this service, and it must not
 * depend on us still existing.
 */
import type { LetterDocument } from './letter';

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const PONZU_SVG = `<svg viewBox="0 0 220 150" width="92" role="img" aria-label="Ponzu the javelina">
<g fill="#3a352d">
<rect x="72" y="96" width="10" height="32" rx="5" opacity="0.72"/><rect x="118" y="96" width="10" height="32" rx="5" opacity="0.72"/>
<rect x="88" y="99" width="10" height="30" rx="5"/><rect x="134" y="99" width="10" height="30" rx="5"/>
<path d="M60 68c-7-4-12-3-15 1 3 4 8 7 14 7z"/><ellipse cx="108" cy="78" rx="52" ry="29"/>
<path d="M66 62l5-14 5 13 6-16 5 15 6-14 5 14 7-15 5 15 7-13 5 13" fill="none" stroke="#3a352d" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M150 62c4-16 20-24 34-18 6 3 12 8 20 11 5 2 5 8 0 9l-16 4c-5 10-16 16-29 15-13-1-13-9-9-21z"/>
<path d="M156 50l3-19 15 13z"/><path d="M176 44l12-17 8 18z"/>
</g>
<path d="M150 60c-4 12-4 20 9 21l-8 20-11-6z" fill="rgba(253,250,244,0.55)"/>
<circle cx="176" cy="56" r="3.1" fill="rgba(253,250,244,0.55)"/>
<path d="M40 30l3.4 8.6L52 42l-8.6 3.4L40 54l-3.4-8.6L28 42l8.6-3.4z" fill="#8d4433"/>
</svg>`;

export function letterToHtml(doc: LetterDocument): string {
  const body = doc.blocks
    .map((block) => {
      if (block.kind === 'paragraph') return `<p>${escapeHtml(block.text)}</p>`;
      const items = block.items.map((i) => `<li>${escapeHtml(i)}</li>`).join('\n        ');
      return `<p class="lead">${escapeHtml(block.lead)}</p>\n      <ul>\n        ${items}\n      </ul>`;
    })
    .join('\n      ');

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Letter to ${escapeHtml(doc.recipientLines[doc.recipientLines.length - 1] ?? 'a neighbor')}</title>
<style>
  @page { size: Letter portrait; margin: 0.75in; }
  html { background: #efe9dc; }
  body {
    margin: 0; padding: 2rem 1rem; color: #23201b; background: #efe9dc;
    font-family: 'Iowan Old Style', Georgia, 'Times New Roman', serif;
    font-size: 11.5pt; line-height: 1.52;
  }
  .sheet {
    background: #fdfaf4; max-width: 8.5in; margin: 0 auto; padding: 0.9in 0.85in 0.8in;
    border: 1px solid #e6dcc9; box-shadow: 0 18px 50px -24px rgba(0,0,0,0.5);
  }
  .date { color: #5d564b; font-size: 10.5pt; margin: 0 0 1.6em; }
  .to { margin: 0 0 1.8em; line-height: 1.45; }
  .to span { display: block; }
  .to span:first-child { color: #5d564b; font-size: 10pt; margin-bottom: 0.35em; }
  p { margin: 0 0 1.05em; }
  .lead { margin-bottom: 0.5em; }
  ul { list-style: none; margin: 0 0 1.05em; padding-left: 1.15em; }
  li { position: relative; margin-bottom: 0.5em; }
  li::before {
    content: ''; position: absolute; left: -0.95em; top: 0.62em; width: 5px; height: 5px;
    border-radius: 50%; background: #8d4433; -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }
  .signoff { margin-top: 1.8em; display: flex; justify-content: space-between; align-items: flex-end; gap: 1.5rem; flex-wrap: wrap; }
  .signoff p { margin: 0; }
  .signoff .name { font-style: italic; margin-top: 0.35em; }
  figure { margin: 0; text-align: center; max-width: 9.5rem; color: #5d564b; }
  figcaption { font-size: 8.5pt; font-style: italic; line-height: 1.35; margin-top: 0.3em; }
  .footer {
    margin-top: 2em; padding-top: 0.85em; border-top: 1px solid #e6dcc9; color: #5d564b;
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif; font-size: 8.5pt; line-height: 1.5;
  }
  .footer p { margin: 0; }
  @media print {
    html, body { background: #fff; padding: 0; }
    .sheet { border: 0; box-shadow: none; padding: 0; max-width: none; }
  }
</style>
</head>
<body>
  <div class="sheet">
    <p class="date">${escapeHtml(doc.date)}</p>
    <div class="to">${doc.recipientLines.map((l) => `<span>${escapeHtml(l)}</span>`).join('')}</div>
    <p>${escapeHtml(doc.salutation)}</p>
      ${body}
    <div class="signoff">
      <div>
        <p>${escapeHtml(doc.signoffLine)}</p>
        <p class="name">${escapeHtml(doc.signoffName)}</p>
      </div>
      <figure>
        ${PONZU_SVG}
        <figcaption>${escapeHtml(doc.mascotCaption)}</figcaption>
      </figure>
    </div>
    <div class="footer"><p>${escapeHtml(doc.footer)}</p></div>
  </div>
</body>
</html>
`;
}

export function downloadLetter(doc: LetterDocument, filename = 'letter.html'): void {
  const blob = new Blob([letterToHtml(doc)], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function suggestedFilename(city: string, zip: string): string {
  const slug = `${city}-${zip}`.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  return `friendly-letter-${slug || 'letter'}.html`;
}
