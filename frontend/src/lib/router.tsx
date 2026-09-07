/**
 * A ~90-line hash router.
 *
 * GitHub Pages serves static files and cannot rewrite unknown paths to
 * index.html, so a history-API router needs the 404.html redirect hack. Hash
 * routing needs nothing: `/#/create` is one document with a fragment, which
 * Pages, a custom domain and a project sub-path all serve identically. That is
 * worth more here than pretty URLs, and it removes a dependency.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export interface RouteLocation {
  path: string;
  query: URLSearchParams;
}

interface RouterValue extends RouteLocation {
  navigate: (to: string, options?: { replace?: boolean }) => void;
}

const RouterContext = createContext<RouterValue | null>(null);

function readLocation(): RouteLocation {
  const raw = window.location.hash.replace(/^#/, '');
  const [rawPath = '', rawQuery = ''] = raw.split('?');
  const path = rawPath.length === 0 ? '/' : rawPath.startsWith('/') ? rawPath : `/${rawPath}`;
  return { path: path.replace(/\/+$/, '') || '/', query: new URLSearchParams(rawQuery) };
}

export function RouterProvider({ children }: { children: ReactNode }) {
  const [location, setLocation] = useState<RouteLocation>(() => readLocation());

  useEffect(() => {
    const onHashChange = () => setLocation(readLocation());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const navigate = useCallback((to: string, options?: { replace?: boolean }) => {
    const target = to.startsWith('#') ? to : `#${to.startsWith('/') ? to : `/${to}`}`;
    if (window.location.hash === target) return;
    if (options?.replace) {
      const url = `${window.location.pathname}${window.location.search}${target}`;
      window.history.replaceState(null, '', url);
      setLocation(readLocation());
    } else {
      window.location.hash = target;
    }
  }, []);

  const value = useMemo<RouterValue>(
    () => ({ ...location, navigate }),
    [location, navigate],
  );

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export function useRouter(): RouterValue {
  const value = useContext(RouterContext);
  if (!value) throw new Error('useRouter must be used inside <RouterProvider>');
  return value;
}

export function useNavigate() {
  return useRouter().navigate;
}

interface LinkProps {
  to: string;
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  ariaLabel?: string;
}

/**
 * Renders a real anchor with a real href so middle-click, "open in new tab" and
 * copy-link all behave, while keeping keyboard activation on the anchor itself.
 */
export function Link({ to, children, className, onClick, ariaLabel }: LinkProps) {
  const { path } = useRouter();
  const href = `#${to.startsWith('/') ? to : `/${to}`}`;
  const isCurrent = path === to.replace(/\/+$/, '');
  return (
    <a
      href={href}
      className={className}
      aria-label={ariaLabel}
      aria-current={isCurrent ? 'page' : undefined}
      onClick={onClick}
    >
      {children}
    </a>
  );
}
