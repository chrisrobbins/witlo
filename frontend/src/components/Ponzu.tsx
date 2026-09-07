/**
 * Ponzu Benedicio — an original javelina, drawn as a single SVG silhouette.
 *
 * Deliberately a silhouette rather than a cartoon: it reads as a woodcut or a
 * postal stamp, which lets it sit on a letter without undermining the letter.
 * The whole animal is one path — body, bristled mane and wedge-shaped head
 * flowing together with no neck, which is what makes a javelina a javelina —
 * plus a clipped pale collar band, the detail that names the species.
 *
 * `tone="ink"` is the version printed on the letter.
 */

export type PonzuTone = 'gold' | 'clay' | 'ink' | 'cream';

const TONES: Record<PonzuTone, { body: string; collar: string; accent: string; eye: string }> = {
  gold: { body: '#e9c46a', collar: 'rgba(11,16,32,0.30)', accent: '#f2d894', eye: '#0b1020' },
  clay: { body: '#cf7256', collar: 'rgba(11,16,32,0.26)', accent: '#e9c46a', eye: '#2a1410' },
  ink: { body: '#3a352d', collar: 'rgba(253,250,244,0.5)', accent: '#8d4433', eye: '#fdfaf4' },
  cream: { body: '#f7efe0', collar: 'rgba(11,16,32,0.2)', accent: '#e9c46a', eye: '#2b2a26' },
};

/**
 * Rump → bristled spine → ears → forehead → snout → jaw → belly → rump.
 * Coordinates are hand-tuned; the zigzag between x=70 and x=150 is the mane.
 */
const BODY_PATH = [
  'M52 94',
  'C44 78 50 62 66 59',
  'L72 47 L79 58',
  'L88 44 L95 57',
  'L106 42 L113 56',
  'L123 43 L130 55',
  'L139 41 L146 53',
  'C154 50 162 49 172 51',
  'C188 54 205 59 223 66',
  'C232 70 232 79 223 81',
  'C212 84 202 86 193 88',
  'C184 95 173 100 161 101',
  'L78 105',
  'C62 105 56 100 52 94',
  'Z',
].join(' ');

/** Two ears, drawn behind the body so their bases vanish into the skull. */
const EAR_PATHS = [
  'M155 55C156 42 164 37 171 43L176 57Z',
  'M179 57C181 45 189 41 196 47L200 61Z',
];

interface PonzuProps {
  tone?: PonzuTone;
  width?: number | string;
  className?: string;
  /** Include the little star he is looking at. */
  star?: boolean;
  title?: string;
}

export function Ponzu({
  tone = 'gold',
  width = 200,
  className,
  star = true,
  title = 'Ponzu, a javelina, looking up at a star',
}: PonzuProps) {
  const c = TONES[tone];
  // Unique-enough id so several Ponzus on one page do not share a clip path.
  const clipId = `ponzu-clip-${tone}`;

  return (
    <svg
      viewBox="0 0 250 150"
      width={width}
      className={className}
      role="img"
      aria-label={title || undefined}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      {title && <title>{title}</title>}
      <defs>
        <clipPath id={clipId}>
          <path d={BODY_PATH} />
        </clipPath>
      </defs>

      <g fill={c.body}>
        {/* far legs, drawn first and dimmed so the near pair reads as nearer */}
        <path d="M74 98h11v33a5.5 5.5 0 0 1-11 0z" opacity="0.45" />
        <path d="M143 96h11v34a5.5 5.5 0 0 1-11 0z" opacity="0.45" />
        {/* tail */}
        <path d="M53 78c-9-2-14-7-12-12 5-1 10 4 14 9z" />
        {/* ears, behind the head */}
        {EAR_PATHS.map((d) => (
          <path key={d} d={d} />
        ))}
        {/* body */}
        <path d={BODY_PATH} />
        {/* near legs */}
        <path d="M92 100h11v32a5.5 5.5 0 0 1-11 0z" />
        <path d="M162 98h11v33a5.5 5.5 0 0 1-11 0z" />
      </g>

      {/* the pale collar, clipped to the body so it never floats free */}
      <g clipPath={`url(#${clipId})`}>
        <path d="M146 30l17-2 22 84-17 3z" fill={c.collar} />
      </g>

      {/* eye and nose */}
      <circle cx="197" cy="63" r="3.2" fill={c.eye} opacity="0.75" />
      <ellipse cx="222" cy="74" rx="4.6" ry="5.4" fill={c.eye} opacity="0.28" />

      {star && (
        <path
          d="M40 26l3.8 9.6L53 39l-9.2 3.4L40 52l-3.8-9.6L27 39l9.2-3.4z"
          fill={c.accent}
        />
      )}
    </svg>
  );
}

/** Compact mark for the header — a star over a low desert horizon. */
export function PonzuMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden="true" focusable="false">
      <rect width="40" height="40" rx="10" fill="#0b1020" stroke="rgba(233,196,106,0.35)" />
      <path d="M20 7.5l2.3 6.2 6.2 2.3-6.2 2.3L20 24.5l-2.3-6.2L11.5 16l6.2-2.3z" fill="#e9c46a" />
      <circle cx="30.5" cy="28.5" r="1.5" fill="#f7efe0" opacity="0.9" />
      <circle cx="10" cy="27" r="1.1" fill="#f7efe0" opacity="0.7" />
      <path
        d="M6 34c3.2-4.2 6.8-6.4 10.4-6.4 3.4 0 5.2 2.2 8.6 2.2 2.8 0 5.2-1.8 9-1.8"
        fill="none"
        stroke="#cf7256"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}
