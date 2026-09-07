import { useMemo, useState } from 'react';
import { Link } from '../lib/router';
import { Ponzu } from '../components/Ponzu';
import { LetterSheet } from '../components/LetterSheet';
import { SectionHead } from '../components/Ui';
import { ArrowRightIcon, BulbIcon, MailIcon, MoonIcon } from '../components/Icons';
import { composeLetter, todayIso } from '../lib/letter';

const EXAMPLE = {
  address: { line1: '414 W San Antonio St', line2: '', city: 'Marfa', state: 'TX', zip: '79843' },
  observations: ['all_night', 'upward'] as const,
  suggestions: ['shield', 'timer', 'warmer_color'] as const,
};

export function Home() {
  const [expanded, setExpanded] = useState(false);
  const example = useMemo(
    () =>
      composeLetter({
        address: EXAMPLE.address,
        observations: [...EXAMPLE.observations],
        note: '',
        suggestions: [...EXAMPLE.suggestions],
        dateIso: todayIso(),
      }),
    [],
  );

  return (
    <>
      <section className="hero">
        <div className="wrap hero__grid">
          <div>
            <p className="eyebrow">A small public service</p>
            <h1>
              A better night starts with <em>a friendly letter.</em>
            </h1>
            <p className="hero__sub">
              Notice a light that might not need to be on? Send a neighbor helpful information
              about light pollution and simple lighting alternatives.
            </p>
            <div className="btn-row">
              <Link to="/create" className="btn btn--primary">
                Create a letter <ArrowRightIcon />
              </Link>
              <Link to="/how-it-works" className="btn btn--secondary">
                See how it works
              </Link>
            </div>
            <p className="hero__note">
              No account. No shaming. No one gets reported. US addresses only, for now.
            </p>
          </div>

          <div className="hero__aside">
            <div className="ponzu-aside">
              <Ponzu tone="gold" width={132} title="Ponzu the javelina, looking up at a star" />
              <p>
                “Smashing the light didn’t help. Asking nicely did.”
                <span>— Ponzu Benedicio, javelina, Marfa, Texas</span>
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="section section--tint" aria-labelledby="how">
        <div className="wrap">
          <SectionHead eyebrow="Three steps, about four minutes" title="How it works" id="how">
            <p>
              You describe what you noticed, we assemble the words, and a paper letter goes in the
              mail. The letter never names you and never accuses anyone.
            </p>
          </SectionHead>

          <div className="card-grid">
            <div className="card">
              <span className="card__num" aria-hidden="true">1</span>
              <h3>Give the address</h3>
              <p>
                The street address of the property with the light. Not your address — yours stays
                with us and never appears on the page.
              </p>
            </div>
            <div className="card">
              <span className="card__num" aria-hidden="true">2</span>
              <h3>Say what you noticed</h3>
              <p>
                A few neutral options: on all night, shining upward, spilling past the property.
                All optional, and phrased as observations rather than complaints.
              </p>
            </div>
            <div className="card">
              <span className="card__num" aria-hidden="true">3</span>
              <h3>Read it, then send it</h3>
              <p>
                You see the exact letter and the exact address before anything happens. Print it
                yourself for free, or have us mail it for you.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="section" aria-labelledby="example">
        <div className="wrap">
          <SectionHead eyebrow="Nothing is hidden" title="This is the letter" id="example">
            <p>
              Every letter is assembled from the same carefully written template. There is no AI
              writing in the loop and no room for an angry paragraph — your choices decide which
              observations and suggestions appear, and that is all.
            </p>
          </SectionHead>

          <div className="sheet-peek" data-expanded={expanded ? 'true' : 'false'}>
            <div className="sheet-scroll">
              <LetterSheet doc={example} id="example-letter" />
            </div>
            <div className="sheet-peek__toggle">
              <button
                type="button"
                className="btn btn--secondary btn--sm"
                aria-expanded={expanded}
                aria-controls="example-letter"
                onClick={() => setExpanded((v) => !v)}
              >
                {expanded ? 'Collapse the letter' : 'Read the whole letter'}
              </button>
            </div>
          </div>

          <div className="btn-row" style={{ marginTop: 'var(--space-6)' }}>
            <Link to="/create" className="btn btn--primary">
              Create your own <ArrowRightIcon />
            </Link>
            <Link to="/why-lighting-matters" className="btn btn--ghost">
              Why any of this matters
            </Link>
          </div>
        </div>
      </section>

      <section className="section section--tint" aria-labelledby="promises">
        <div className="wrap">
          <SectionHead eyebrow="What this is not" title="A few firm promises" id="promises" />
          <div className="card-grid">
            <div className="card">
              <p style={{ color: 'var(--gold-400)', marginBottom: 'var(--space-3)' }}>
                <MoonIcon size={22} />
              </p>
              <h3>Not a complaint line</h3>
              <p>
                Nothing is reported to a city, a landlord, or the police. There is no map, no
                public list of addresses, and no way to look up who sent what.
              </p>
            </div>
            <div className="card">
              <p style={{ color: 'var(--gold-400)', marginBottom: 'var(--space-3)' }}>
                <BulbIcon size={22} />
              </p>
              <h3>Not anti-light</h3>
              <p>
                Outdoor lighting keeps people safe and independent. The letter asks about
                <em> unnecessary</em> light — the part that goes up, or sideways, or shines on an
                empty lot at 3 a.m.
              </p>
            </div>
            <div className="card">
              <p style={{ color: 'var(--gold-400)', marginBottom: 'var(--space-3)' }}>
                <MailIcon size={22} />
              </p>
              <h3>Not a mystery</h3>
              <p>
                One letter per address, with a long cooldown before another. Any recipient can ask
                us never to write to that address again, and we will honor it.
              </p>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
