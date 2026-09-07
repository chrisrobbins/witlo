import { useEffect } from 'react';
import { RouterProvider, useRouter } from './lib/router';
import { StarField } from './components/StarField';
import { DemoBanner, SiteFooter, SiteHeader } from './components/Layout';
import { Home } from './routes/Home';
import { HowItWorks, Learn } from './routes/Learn';
import { Faq } from './routes/Faq';
import { Create } from './routes/Create';
import { NoMoreLetters, Privacy, Terms } from './routes/Legal';
import { NotFound, Receipt } from './routes/Receipt';

const TITLES: Record<string, string> = {
  '/': 'A better night starts with a friendly letter',
  '/how-it-works': 'How it works',
  '/why-lighting-matters': 'Why lighting matters',
  '/faq': 'Questions',
  '/create': 'Create a letter',
  '/receipt': 'Your receipt',
  '/privacy': 'Privacy',
  '/terms': 'Terms',
  '/no-more-letters': 'No more letters',
};

function Routes() {
  const { path } = useRouter();

  useEffect(() => {
    const title = TITLES[path];
    document.title = title
      ? `${title} — Why Is This Light On?`
      : 'Why Is This Light On?';
  }, [path]);

  switch (path) {
    case '/':
      return <Home />;
    case '/how-it-works':
      return <HowItWorks />;
    case '/why-lighting-matters':
      return <Learn />;
    case '/faq':
      return <Faq />;
    case '/create':
      return <Create />;
    case '/receipt':
      return <Receipt />;
    case '/privacy':
      return <Privacy />;
    case '/terms':
      return <Terms />;
    case '/no-more-letters':
      return <NoMoreLetters />;
    default:
      return <NotFound />;
  }
}

export function App() {
  return (
    <RouterProvider>
      <StarField />
      <a className="skip-link" href="#main">
        Skip to the main content
      </a>
      <div className="app">
        <div className="no-print">
          <DemoBanner />
          <SiteHeader />
        </div>
        <main className="app__main" id="main" tabIndex={-1}>
          <Routes />
        </main>
        <SiteFooter />
      </div>
    </RouterProvider>
  );
}
