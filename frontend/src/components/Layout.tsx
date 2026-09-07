import { Link } from '../lib/router';
import { IS_DEMO, SITE_NAME } from '../lib/config';
import { PonzuMark } from './Ponzu';

export function DemoBanner() {
  if (!IS_DEMO) return null;
  return (
    <div className="demo-banner" role="status">
      <div className="wrap demo-banner__inner">
        <span className="demo-banner__dot" aria-hidden="true" />
        <p style={{ margin: 0, maxWidth: 'none' }}>
          <strong>Demo mode.</strong> You can write and print a complete letter here, but{' '}
          <strong>nothing will be mailed and no payment will be taken</strong> — this build has no
          mailing service connected.
        </p>
      </div>
    </div>
  );
}

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="wrap site-header__inner">
        <Link to="/" className="brand" ariaLabel={`${SITE_NAME} — home`}>
          <PonzuMark className="brand__mark" />
          <span className="brand__text">
            Why Is This Light On?
            <small>A friendly letter about the night sky</small>
          </span>
        </Link>
        <nav className="site-nav" aria-label="Main">
          <Link to="/how-it-works">How it works</Link>
          <Link to="/why-lighting-matters">Why lighting matters</Link>
          <Link to="/faq">FAQ</Link>
          <Link to="/create">Create a letter</Link>
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="site-footer no-print">
      <div className="wrap">
        <div className="site-footer__grid">
          <div>
            <p style={{ fontFamily: 'var(--font-display)', fontSize: 'var(--step-1)', color: 'var(--cream-100)' }}>
              A better night starts with a friendly letter.
            </p>
            <p className="muted" style={{ marginBottom: 0 }}>
              A small public-service project, and the constructive half of a story about a javelina
              named Ponzu who learned that talking works better than smashing.
            </p>
          </div>
          <div>
            <h4>The service</h4>
            <ul>
              <li><Link to="/create">Create a letter</Link></li>
              <li><Link to="/how-it-works">How it works</Link></li>
              <li><Link to="/faq">FAQ</Link></li>
            </ul>
          </div>
          <div>
            <h4>Learn</h4>
            <ul>
              <li><Link to="/why-lighting-matters">Why lighting matters</Link></li>
              <li>
                <a href="https://darksky.org" target="_blank" rel="noreferrer noopener">
                  DarkSky International
                </a>
              </li>
            </ul>
          </div>
          <div>
            <h4>Fine print</h4>
            <ul>
              <li><Link to="/privacy">Privacy</Link></li>
              <li><Link to="/terms">Terms</Link></li>
              <li><Link to="/no-more-letters">No more letters</Link></li>
            </ul>
          </div>
        </div>

        <div className="site-footer__colophon">
          <p>
            © {new Date().getFullYear()} Why Is This Light On?. Ponzu Benedicio and the
            surrounding story are original characters.
          </p>
        </div>
      </div>
    </footer>
  );
}
