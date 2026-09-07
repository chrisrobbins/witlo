interface IconProps {
  size?: number;
  className?: string;
}

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: '0 0 24 24',
  fill: 'none' as const,
  stroke: 'currentColor',
  strokeWidth: 1.9,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
  focusable: 'false' as const,
});

export const CheckIcon = ({ size = 14, className }: IconProps) => (
  <svg {...base(size)} strokeWidth={3} className={className}>
    <path d="M4 12.5l5 5 11-11" />
  </svg>
);

export const ArrowRightIcon = ({ size = 18, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M4 12h15M13 6l6 6-6 6" />
  </svg>
);

export const ArrowLeftIcon = ({ size = 18, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M20 12H5M11 6l-6 6 6 6" />
  </svg>
);

export const InfoIcon = ({ size = 18, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5M12 7.6v.4" />
  </svg>
);

export const AlertIcon = ({ size = 18, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M12 4.5l8.5 15h-17z" />
    <path d="M12 10v4M12 17.2v.3" />
  </svg>
);

export const PrintIcon = ({ size = 18, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M7 9V3.5h10V9" />
    <rect x="3.5" y="9" width="17" height="8" rx="2" />
    <path d="M7 14h10v6.5H7z" />
  </svg>
);

export const DownloadIcon = ({ size = 18, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M12 3.5v11M7.5 10.5L12 15l4.5-4.5" />
    <path d="M4.5 17.5v1.2a1.8 1.8 0 001.8 1.8h11.4a1.8 1.8 0 001.8-1.8v-1.2" />
  </svg>
);

export const MailIcon = ({ size = 18, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <rect x="3" y="5.5" width="18" height="13" rx="2" />
    <path d="M3.6 7l8.4 6 8.4-6" />
  </svg>
);

export const StarIcon = ({ size = 18, className }: IconProps) => (
  <svg viewBox="0 0 24 24" width={size} height={size} className={className} aria-hidden focusable="false">
    <path
      d="M12 2.6l2.5 6.4 6.9 0.5-5.3 4.4 1.7 6.7L12 16.9 6.2 20.6l1.7-6.7L2.6 9.5l6.9-0.5z"
      fill="currentColor"
    />
  </svg>
);

export const MoonIcon = ({ size = 18, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M20 14.4A8.4 8.4 0 019.6 4a8.4 8.4 0 1010.4 10.4z" />
  </svg>
);

export const BulbIcon = ({ size = 18, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M9.2 17.5h5.6M10 20.5h4" />
    <path d="M12 3.5a5.8 5.8 0 013.4 10.5c-.6.5-.9 1-.9 1.7H9.5c0-.7-.3-1.2-.9-1.7A5.8 5.8 0 0112 3.5z" />
  </svg>
);
