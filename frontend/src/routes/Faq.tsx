import type { ReactNode } from 'react';
import { Link } from '../lib/router';
import { ArrowRightIcon } from '../components/Icons';

interface QA {
  q: string;
  a: ReactNode;
}

const QUESTIONS: QA[] = [
  {
    q: 'What is light pollution?',
    a: (
      <>
        <p>
          DarkSky International defines it as the human-made alteration of outdoor light levels
          from those occurring naturally. In practice it shows up as sky glow over a town, light
          trespassing onto property where it was not wanted, glare that makes it harder rather than
          easier to see, and clutter — too many light sources competing.
        </p>
        <p>
          It is worth knowing that it is also reversible. Unlike most pollution, the effect stops
          the moment the cause does.{' '}
          <Link to="/why-lighting-matters">More detail, with sources.</Link>
        </p>
      </>
    ),
  },
  {
    q: 'Do all outdoor lights need to be turned off?',
    a: (
      <>
        <p>
          No, and this service would be doing harm if it suggested so. Outdoor lighting helps people
          find steps and doorways, supports accessibility, and matters a great deal to how safe
          people feel where they live. Some lights are exactly where they should be.
        </p>
        <p>
          The question a letter raises is narrower: is any of this light going somewhere it is not
          useful — into the sky, across the road, onto an empty lot at three in the morning? That
          part can usually be improved without giving up anything.
        </p>
      </>
    ),
  },
  {
    q: 'What lighting alternatives can help?',
    a: (
      <>
        <p>
          The most effective single change is usually shielding: a fixture that is covered on top
          and aimed down puts its light on the ground instead of in the sky. After that, timers and
          motion sensors so the light works when people do, a dimmer or lower-output bulb, and
          warmer-colored light — DarkSky recommends 3000 kelvin or lower for outdoor use.
        </p>
        <p>
          A letter carries whichever of these you choose, and none of them require replacing a
          whole fixture.
        </p>
      </>
    ),
  },
  {
    q: 'What does the letter say?',
    a: (
      <>
        <p>
          You can read the whole thing on the home page before you type anything. In short: a
          neighbor noticed an outdoor light; here is specifically what they noticed; outdoor
          lighting serves real purposes and this is not a judgment; here is what light pollution is
          in plain language; here are some practical alternatives; thank you for reading.
        </p>
        <p>
          It is assembled from a fixed template — there is no AI writing the words, and no way for
          an angry sentence to end up in someone's mailbox. Your optional note is the only free
          text, it is capped and checked, and you see it in the preview before anything is sent.
        </p>
      </>
    ),
  },
  {
    q: 'Will the recipient know who sent it?',
    a: (
      <>
        <p>
          No. Your name and your home address are never printed on the letter and are never given
          to the recipient. The letter is signed “a neighbor, by way of Why Is This Light On?” and
          explains what the service is, so the reader knows where it came from without knowing who
          asked for it.
        </p>
        <p>
          If our mailing provider requires a return address for postal purposes, we use the
          service's own address, never yours. Give this a moment's thought all the same: a very
          specific note about a very specific fixture can identify the person who wrote it in a
          small town.
        </p>
      </>
    ),
  },
  {
    q: 'Does this guarantee a lighting change?',
    a: (
      <p>
        No. It is a letter. Some people will read it, think about it and adjust something; some
        will read it and decide the light stays, which is entirely their call; some will not read
        it at all. We have no way to follow up, no enforcement of any kind, and no interest in
        having either. If a guaranteed outcome is what you need, this is the wrong tool.
      </p>
    ),
  },
  {
    q: 'Can children use this with a grown-up?',
    a: (
      <>
        <p>
          Yes, and it is a good project to do together — noticing lights on a walk, deciding which
          suggestions fit, reading the letter aloud before it goes. That is close to the whole point
          of the story this comes from.
        </p>
        <p>
          A grown-up should be the one to enter an address and, if the letter is being mailed, to
          approve the payment. We do not knowingly collect information from children, and the free
          print-it-yourself path needs no email address at all.
        </p>
      </>
    ),
  },
  {
    q: 'Can I stop receiving letters at my address?',
    a: (
      <p>
        Yes. <Link to="/no-more-letters">Ask us here</Link> and that address goes on a do-not-mail
        list that this service checks before it prints anything. It is the only list we keep, and
        it exists to prevent letters, not to enable them.
      </p>
    ),
  },
];

export function Faq() {
  return (
    <div className="section">
      <div className="wrap-narrow">
        <p className="eyebrow">Questions</p>
        <h1>Reasonable things to ask first</h1>
        <p className="lede">
          Including the ones where the honest answer is “no” or “we can't promise that”.
        </p>

        <div className="faq" style={{ marginTop: 'var(--space-6)' }}>
          {QUESTIONS.map((item) => (
            <details key={item.q}>
              <summary>{item.q}</summary>
              <div className="faq__body">{item.a}</div>
            </details>
          ))}
        </div>

        <div className="btn-row" style={{ marginTop: 'var(--space-7)' }}>
          <Link to="/create" className="btn btn--primary">
            Create a letter <ArrowRightIcon />
          </Link>
          <Link to="/privacy" className="btn btn--ghost">
            What we collect
          </Link>
        </div>
      </div>
    </div>
  );
}
