"""Renders a composed letter to the print-ready HTML the provider prints.

This is the one place where letter content becomes markup, so it is the one
place where escaping matters. Every interpolated value goes through `esc`; the
template itself is a constant. Nothing here accepts HTML from anywhere.

The layout mirrors `frontend/src/lib/download.ts` so the page a sender printed
themselves and the page the provider prints are the same document.
"""

from __future__ import annotations

from html import escape

from .composer import LetterDocument, Paragraph

#: Lob prints the recipient block through an envelope window on the first page,
#: so the top of page one must stay clear. 2.5 inches is their published
#: requirement for `address_placement: top_first_page`.
ADDRESS_WINDOW_INCHES = 2.5

PONZU_SVG = (
    '<svg viewBox="0 0 250 150" width="78" xmlns="http://www.w3.org/2000/svg">'
    '<defs><clipPath id="pz"><path d="M52 94C44 78 50 62 66 59L72 47 79 58L88 44 95 57'
    "L106 42 113 56L123 43 130 55L139 41 146 53C154 50 162 49 172 51C188 54 205 59 223 66"
    'C232 70 232 79 223 81C212 84 202 86 193 88C184 95 173 100 161 101L78 105C62 105 56 100 52 94Z"/>'  # noqa: E501
    "</clipPath></defs>"
    '<g fill="#3a352d">'
    '<path d="M74 98h11v33a5.5 5.5 0 0 1-11 0z" opacity="0.45"/>'
    '<path d="M143 96h11v34a5.5 5.5 0 0 1-11 0z" opacity="0.45"/>'
    '<path d="M53 78c-9-2-14-7-12-12 5-1 10 4 14 9z"/>'
    '<path d="M155 55C156 42 164 37 171 43L176 57Z"/>'
    '<path d="M179 57C181 45 189 41 196 47L200 61Z"/>'
    '<path d="M52 94C44 78 50 62 66 59L72 47 79 58L88 44 95 57L106 42 113 56L123 43 130 55'
    "L139 41 146 53C154 50 162 49 172 51C188 54 205 59 223 66C232 70 232 79 223 81"
    'C212 84 202 86 193 88C184 95 173 100 161 101L78 105C62 105 56 100 52 94Z"/>'
    '<path d="M92 100h11v32a5.5 5.5 0 0 1-11 0z"/>'
    '<path d="M162 98h11v33a5.5 5.5 0 0 1-11 0z"/>'
    "</g>"
    '<g clip-path="url(#pz)"><path d="M146 30l17-2 22 84-17 3z" fill="rgba(253,250,244,0.5)"/></g>'
    '<circle cx="197" cy="63" r="3.2" fill="#fdfaf4" opacity="0.75"/>'
    '<path d="M40 26l3.8 9.6L53 39l-9.2 3.4L40 52l-3.8-9.6L27 39l9.2-3.4z" fill="#8d4433"/>'
    "</svg>"
)

_CSS = """
  @page { size: Letter; margin: 0; }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: #fff; color: #1a1a1a; }
  body {
    font-family: 'Iowan Old Style', Georgia, 'Times New Roman', serif;
    font-size: 10.4pt; line-height: 1.46;
  }
  .page { width: 8.5in; min-height: 11in; padding: 0 0.75in 0.7in; }
  /* Keep the top of page one clear for the address window. */
  .window { height: %(window)sin; padding: 0.55in 0.75in 0; }
  .window .date { color: #555; font-size: 9.5pt; margin: 0; }
  p { margin: 0 0 1.05em; }
  .lead { margin-bottom: 0.5em; }
  ul { list-style: none; margin: 0 0 1.05em; padding-left: 1.1em; }
  li { position: relative; margin-bottom: 0.5em; }
  li::before {
    content: ''; position: absolute; left: -0.9em; top: 0.62em; width: 4.5px; height: 4.5px;
    border-radius: 50%%; background: #8d4433;
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }
  .signoff {
    margin-top: 1.3em; display: flex; justify-content: space-between;
    align-items: flex-end; gap: 1.2rem;
  }
  .signoff p { margin: 0; }
  .signoff .name { font-style: italic; margin-top: 0.3em; }
  figure { margin: 0; text-align: center; max-width: 1.5in; color: #555; }
  figcaption { font-size: 7.5pt; font-style: italic; line-height: 1.3; margin-top: 0.2em; }
  .footer {
    margin-top: 1.3em; padding-top: 0.7em; border-top: 1px solid #ddd; color: #555;
    font-family: Helvetica, Arial, sans-serif; font-size: 7.6pt; line-height: 1.45;
  }
  .footer p { margin: 0; }
"""


def esc(value: str) -> str:
    return escape(value, quote=True)


def render_letter_html(doc: LetterDocument) -> str:
    """Full HTML document, self-contained, safe to hand to the print provider."""
    body_parts: list[str] = []
    for block in doc.blocks:
        if isinstance(block, Paragraph):
            body_parts.append(f"<p>{esc(block.text)}</p>")
        else:
            items = "".join(f"<li>{esc(item)}</li>" for item in block.items)
            body_parts.append(f'<p class="lead">{esc(block.lead)}</p><ul>{items}</ul>')

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{esc(doc.signoff_name)}</title>"
        f"<style>{_CSS % {'window': ADDRESS_WINDOW_INCHES}}</style>"
        "</head><body>"
        f'<div class="window"><p class="date">{esc(doc.date)}</p></div>'
        '<div class="page">'
        f"<p>{esc(doc.salutation)}</p>"
        f"{''.join(body_parts)}"
        '<div class="signoff"><div>'
        f"<p>{esc(doc.signoff_line)}</p>"
        f'<p class="name">{esc(doc.signoff_name)}</p>'
        "</div>"
        f"<figure>{PONZU_SVG}<figcaption>{esc(doc.mascot_caption)}</figcaption></figure>"
        "</div>"
        f'<div class="footer"><p>{esc(doc.footer)}</p></div>'
        "</div></body></html>"
    )
