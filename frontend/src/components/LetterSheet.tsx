/**
 * Renders a composed LetterDocument as a page of paper.
 *
 * Nothing is interpolated as HTML: every string comes from the shared template
 * file or from the sanitized note, and React escapes all of it. This component
 * is also what the print stylesheet targets, so what you see is what prints.
 */
import type { LetterDocument } from '../lib/letter';
import { Ponzu } from './Ponzu';

export function LetterSheet({
  doc,
  id = 'letter-sheet',
}: {
  doc: LetterDocument;
  id?: string;
}) {
  return (
    <article className="sheet" id={id} aria-label="Letter preview">
      <p className="sheet__date">{doc.date}</p>

      <div className="sheet__to">
        {doc.recipientLines.map((line, i) => (
          <span key={i}>{line}</span>
        ))}
      </div>

      <p className="sheet__salutation">{doc.salutation}</p>

      <div className="sheet__body">
        {doc.blocks.map((block, i) =>
          block.kind === 'paragraph' ? (
            <p key={i}>{block.text}</p>
          ) : (
            <div key={i}>
              <p className="sheet__list-lead">{block.lead}</p>
              <ul className="sheet__list">
                {block.items.map((item, j) => (
                  <li key={j}>{item}</li>
                ))}
              </ul>
            </div>
          ),
        )}
      </div>

      <div className="sheet__signoff">
        <div className="sheet__signoff-text">
          <p>{doc.signoffLine}</p>
          <p className="sheet__signoff-name">{doc.signoffName}</p>
        </div>
        <figure className="sheet__mascot">
          <Ponzu tone="ink" width={92} star title="" />
          <figcaption>{doc.mascotCaption}</figcaption>
        </figure>
      </div>

      <div className="sheet__footer">
        <p>{doc.footer}</p>
      </div>
    </article>
  );
}

/** The address block as it will appear through the envelope window. */
export function EnvelopePreview({ lines }: { lines: string[] }) {
  return (
    <div className="envelope-preview">
      <p className="envelope-preview__label">Addressed to</p>
      {lines.map((line, i) => (
        <div key={i}>{line}</div>
      ))}
    </div>
  );
}
