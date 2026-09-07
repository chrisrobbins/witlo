/**
 * The night sky behind everything.
 *
 * Stars are generated once from a fixed seed so the sky is identical on every
 * render and every reload — a sky that reshuffles on navigation is distracting,
 * and a deterministic one also makes visual regression screenshots stable.
 * Twinkling is CSS-only and disabled under `prefers-reduced-motion`.
 */
import { useMemo, type CSSProperties } from 'react';

function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

interface Star {
  x: number;
  y: number;
  r: number;
  o: number;
  delay: number;
}

function makeStars(count: number, seed: number): Star[] {
  const rand = mulberry32(seed);
  const stars: Star[] = [];
  for (let i = 0; i < count; i += 1) {
    const y = Math.pow(rand(), 1.35) * 100; // denser near the top of the sky
    stars.push({
      x: rand() * 100,
      y,
      r: 0.35 + rand() * 1.15,
      o: 0.25 + rand() * 0.6,
      delay: rand() * 6,
    });
  }
  return stars;
}

export function StarField() {
  const stars = useMemo(() => makeStars(160, 20260907), []);

  return (
    <div className="sky" aria-hidden="true">
      <svg
        className="sky__stars"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        focusable="false"
      >
        {stars.map((s, i) => (
          <circle
            key={i}
            className="sky__star"
            cx={s.x}
            cy={s.y}
            r={s.r * 0.12}
            fill="#f7efe0"
            style={
              {
                opacity: s.o,
                animationDelay: `${s.delay}s`,
                ['--o' as string]: String(s.o),
              } as CSSProperties
            }
          />
        ))}
        {/* one slow shooting star, purely decorative */}
        <path d="M78 8 L84 5" stroke="rgba(247,239,224,0.5)" strokeWidth="0.18" />
      </svg>

      <svg
        className="sky__horizon"
        viewBox="0 0 1200 240"
        preserveAspectRatio="none"
        focusable="false"
      >
        <path
          d="M0 240V166c58-4 92-30 140-30 44 0 66 20 108 20 40 0 58-34 104-34 40 0 62 26 104 26 46 0 72-40 124-40 48 0 74 30 118 30 40 0 62-22 102-22 46 0 70 26 118 26 44 0 68-18 110-18 34 0 58 10 84 16V240z"
          fill="#070b18"
          opacity="0.85"
        />
        <path
          d="M0 240V196c70-8 110-22 168-22 52 0 84 16 132 16 44 0 76-22 128-22 48 0 78 20 126 20 52 0 84-24 138-24 50 0 80 18 130 18 46 0 76-12 122-12 42 0 178 14 178 14V240z"
          fill="#050810"
        />
      </svg>
    </div>
  );
}
