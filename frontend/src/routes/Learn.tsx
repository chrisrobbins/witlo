import { Link } from '../lib/router';
import { Callout } from '../components/Ui';
import { ArrowRightIcon } from '../components/Icons';
import { Ponzu } from '../components/Ponzu';
import { CONTENT, SUGGESTION_ORDER } from '../lib/letterContent';

const DARKSKY = 'https://darksky.org';

export function Learn() {
  return (
    <div className="section">
      <div className="wrap-narrow">
        <p className="eyebrow">Why lighting matters</p>
        <h1>Light is not the problem. Wasted light is.</h1>
        <p className="lede">
          Almost everything on this page comes from DarkSky International, the organization that
          has done the most to turn night-sky protection into practical lighting advice. Where we
          state a number, we link to their source.
        </p>

        <hr />

        <h2>What light pollution is</h2>
        <p>
          DarkSky defines light pollution as{' '}
          <strong>the human-made alteration of outdoor light levels from those occurring naturally</strong>.
          It is usually broken into four kinds, and most outdoor fixtures produce at least one of
          them without anyone intending it:
        </p>
        <ul>
          <li>
            <strong>Sky glow</strong> — the brightening of the night sky over a town, which is why
            a city's glow is visible from far outside it.
          </li>
          <li>
            <strong>Light trespass</strong> — light falling where it was not wanted or needed, such
            as through a neighbor's bedroom window.
          </li>
          <li>
            <strong>Glare</strong> — brightness harsh enough to cause discomfort and, at night,
            to make it genuinely harder to see.
          </li>
          <li>
            <strong>Clutter</strong> — confusing, excessive groupings of light sources.
          </li>
        </ul>

        <p>
          DarkSky estimates that about <strong>80 percent of the world's population lives under sky
          glow</strong>, and that in the United States and Europe roughly 99 percent of people
          cannot experience a truly natural night.
        </p>

        <Callout tone="ok" title="The genuinely good news">
          <p style={{ marginBottom: 0 }}>
            Light pollution is one of the few kinds of pollution that is immediately reversible.
            Nothing has to be cleaned up or decay away. A shielded fixture, a dimmer bulb or a
            timer changes the sky above that street the same night.
          </p>
        </Callout>

        <h2>What it affects</h2>
        <p>
          DarkSky documents effects across wildlife and ecosystems, human health, energy use and
          climate, crime and safety, and what they call night sky heritage. Two of those deserve a
          careful word.
        </p>
        <p>
          <strong>Wildlife</strong> is the least ambiguous. Migrating birds, insects and
          pollinators, sea turtles and nocturnal mammals all use darkness as information, and
          artificial light at night interferes with it. In West Texas this is not abstract: the
          moths that show up around a porch light are moths that are not doing anything else that
          night.
        </p>
        <p>
          <strong>Crime and safety</strong> is where careful language matters. The intuition that
          more light always means more safety is not as well supported as most people assume, and
          the research is genuinely mixed. We do not claim that turning a light off makes a place
          safer, and neither should a letter. What is well established is that glare hurts
          visibility, and that a light which blinds you is not helping you see.
        </p>

        <h2>What actually helps</h2>
        <p>
          DarkSky's five principles for responsible outdoor lighting are the clearest summary
          anyone has produced, and every suggestion this service offers is one of them in plain
          clothes:
        </p>
        <ol>
          <li><strong>Useful</strong> — use light only if it is needed.</li>
          <li><strong>Targeted</strong> — direct light so it falls only where it is needed.</li>
          <li><strong>Low level</strong> — light should be no brighter than necessary.</li>
          <li><strong>Controlled</strong> — use light only when it is needed.</li>
          <li><strong>Warm-colored</strong> — use warmer-color lights where possible.</li>
        </ol>
        <p>
          For a home specifically, DarkSky recommends shielded fixtures aimed downward, timers for
          porch lights and occupancy sensors for security lights, a dimmer or lower-wattage bulb
          rather than the brightest available, and — when a bulb needs replacing —{' '}
          <strong>3000 kelvin or lower</strong>.
        </p>

        <div className="panel panel--flat" style={{ marginBlock: 'var(--space-6)' }}>
          <h3 style={{ fontSize: 'var(--step-1)' }}>The six suggestions a letter can carry</h3>
          <ul style={{ marginBottom: 0 }}>
            {SUGGESTION_ORDER.map((key) => (
              <li key={key}>
                <strong>{CONTENT.suggestions[key].label}.</strong>{' '}
                <span className="muted">{CONTENT.suggestions[key].bullet}</span>
              </li>
            ))}
          </ul>
        </div>

        <h2>What one letter can honestly claim</h2>
        <p>
          Not very much, and that is fine. One shielded floodlight will not bring the Milky Way
          back over a town, and we will not tell you otherwise. What a letter can do is put good
          information in front of someone who very likely has never been asked to think about it,
          in a form that is easy to act on and impossible to take as an accusation. Sometimes that
          is enough. Often it is not. It is still the best available move.
        </p>

        <div className="ponzu-aside" style={{ marginBlock: 'var(--space-6)' }}>
          <Ponzu tone="clay" width={110} star={false} title="" />
          <p>
            Ponzu tried the other approach first.
            <span>
              It went poorly for the hardware store, and worse for the neighbors who needed the
              light by the ramp.
            </span>
          </p>
        </div>

        <div className="source-note">
          <p><strong>Sources.</strong> Everything above is drawn from DarkSky International:</p>
          <ul>
            <li>
              <a href={`${DARKSKY}/resources/what-is-light-pollution/`} target="_blank" rel="noreferrer noopener">
                What is light pollution?
              </a>{' '}
              — definition, the four components, the 80% and 99% figures, reversibility.
            </li>
            <li>
              <a href={`${DARKSKY}/resources/what-is-light-pollution/effects/`} target="_blank" rel="noreferrer noopener">
                Effects of light pollution
              </a>{' '}
              — wildlife, health, energy and climate, crime and safety, night sky heritage.
            </li>
            <li>
              <a href={`${DARKSKY}/resources/guides-and-how-tos/lighting-principles/`} target="_blank" rel="noreferrer noopener">
                Five principles for responsible outdoor lighting
              </a>
            </li>
            <li>
              <a href={`${DARKSKY}/what-we-do/advancing-responsible-outdoor-lighting/home/`} target="_blank" rel="noreferrer noopener">
                Responsible home outdoor lighting
              </a>{' '}
              — shielding, timers and occupancy sensors, dimmers, 3000 K or lower.
            </li>
          </ul>
          <p style={{ marginBottom: 0 }}>
            This project is not affiliated with or endorsed by DarkSky International.
          </p>
        </div>

        <div className="btn-row">
          <Link to="/create" className="btn btn--primary">
            Create a letter <ArrowRightIcon />
          </Link>
          <Link to="/faq" className="btn btn--ghost">
            Read the FAQ
          </Link>
        </div>
      </div>
    </div>
  );
}

export function HowItWorks() {
  return (
    <div className="section">
      <div className="wrap-narrow">
        <p className="eyebrow">How it works</p>
        <h1>Four screens, one envelope</h1>
        <p className="lede">
          The whole point is that nothing surprising happens. Here is every step, including the
          parts most services would rather you did not think about.
        </p>

        <hr />

        <h2>1. You give the address of the property</h2>
        <p>
          Street address, city, state, ZIP — US addresses only for now, because that is where our
          mailing service prints and posts. You never give us the address of the person the light
          is bothering, including your own.
        </p>

        <h2>2. You say what you noticed</h2>
        <p>
          Four neutral checkboxes and one optional free-text note, capped at{' '}
          {CONTENT.limits.note_max_chars} characters. Everything here is optional. The letter
          describes these as things a neighbor noticed from the street on one occasion, because
          that is all anyone can honestly say.
        </p>

        <h2>3. You choose which suggestions to offer</h2>
        <p>
          Six practical alternatives, all drawn from DarkSky International's lighting principles.
          Two or three specific ideas read better than a list of six.
        </p>

        <h2>4. You read the whole letter, then decide</h2>
        <p>
          The preview is the letter — same words, same address block, same page. From there you can
          print it or download it for free and post it yourself, or, where a mailing service is
          connected, pay the exact posted price and have us print and mail it.
        </p>

        <Callout tone="gold" title="What the letter never does">
          <ul style={{ marginBottom: 0 }}>
            <li>It never names you, and never carries your address.</li>
            <li>It never says the light is illegal, or implies anyone will be reported.</li>
            <li>It never asserts anything about the property beyond what you observed.</li>
            <li>It never invents the recipient's name — it is addressed to the resident or property manager.</li>
          </ul>
        </Callout>

        <h2>If it is mailed</h2>
        <p>
          Payment goes through Stripe's own hosted page; we never see a card number. Your letter is
          printed only after Stripe tells our server directly that the payment succeeded — the
          "thank you" screen in your browser is not what triggers it. You then get a receipt and a
          status page that says exactly what happened, in words that distinguish{' '}
          <em>handed to the mailing provider</em> from <em>delivered</em>, because those are not
          the same thing and no one can promise the second.
        </p>

        <div className="btn-row" style={{ marginTop: 'var(--space-6)' }}>
          <Link to="/create" className="btn btn--primary">
            Create a letter <ArrowRightIcon />
          </Link>
          <Link to="/why-lighting-matters" className="btn btn--ghost">
            Why lighting matters
          </Link>
        </div>
      </div>
    </div>
  );
}
