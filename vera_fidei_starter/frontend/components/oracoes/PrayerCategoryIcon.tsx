interface PrayerCategoryIconProps {
  code: string
  className?: string
}

/** Compact devotional glyphs drawn for the prayer-category medallions. */
export default function PrayerCategoryIcon({
  code,
  className = '',
}: PrayerCategoryIconProps) {
  const common = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.45,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    className,
    'aria-hidden': true,
    focusable: false,
  }

  switch (code) {
    case 'MARIA':
      return (
        <svg {...common}>
          <ellipse cx="12" cy="4.1" rx="4.1" ry="1.45" />
          <path d="M12.7 6.2c2 .1 3.2 1.2 3.2 2.8l1.25 1.05-1.3.75c-.2 1.65-1.1 2.65-2.55 3.15" />
          <path d="M10.4 6.35C7.5 8.6 6.35 13.1 6.7 20.5h11c.1-3.65-.65-6.35-2.2-8.15" />
          <path d="M9.4 13.15c.55 1.55 1.65 2.55 3.25 2.95M9.8 20.5c.4-2.1 1.35-3.55 2.85-4.4" />
        </svg>
      )
    case 'DIV':
      return (
        <svg {...common}>
          <path d="M12 2.5v15M8.7 6.5h6.6M9.6 17.5h4.8" />
          <path d="M3.5 18.5c1.8-3.8 3.55-5.7 5.25-5.7.5 0 .85.45.7.95l-.8 2.75 3.35 3.1" />
          <path d="M20.5 18.5c-1.8-3.8-3.55-5.7-5.25-5.7-.5 0-.85.45-.7.95l.8 2.75L12 19.6" />
          <path d="m5 20 3 1.5 4-1.9 4 1.9 3-1.5" />
        </svg>
      )
    case 'JOSE':
      return (
        <svg {...common}>
          <path d="M8.7 21.5c1.25-5.15 2.55-9.95 4.4-15.6" />
          <path d="M13.1 6c-2.05-.15-3.35-1.2-3.8-3 1.8-.3 3.15.45 4.05 2.15.15-1.9 1.05-3 2.75-3.4.65 1.75-.35 3.55-3 4.25Z" />
          <path d="M10.65 13.1c-2.1-.05-3.55-.9-4.35-2.55 1.65-.7 3.2-.2 4.65 1.45M11.85 9.7c1.45-1.55 3.05-1.95 4.8-1.2-.8 1.6-2.25 2.4-4.35 2.35" />
          <path d="M9.75 16.6c-1.85.2-3.2-.35-4.05-1.65 1.3-.85 2.8-.55 4.5.9M10.9 13.4c1.5.15 2.6.85 3.3 2.1-1.25.65-2.55.35-3.9-.85" />
        </svg>
      )
    case 'EUCA':
      return (
        <svg {...common}>
          <circle cx="12" cy="4.8" r="3.25" />
          <path d="M12 3.15v3.3M10.35 4.8h3.3" />
          <path d="M6.4 9.2h11.2l-.9 4.25a4.8 4.8 0 0 1-9.4 0L6.4 9.2Z" />
          <path d="M12 18.2v3.3M8.7 21.5h6.6" />
        </svg>
      )
    case 'ESP':
      return (
        <svg {...common}>
          <path
            d="M2.35 12.25c4.95 1.15 8.2-.35 9.6-5.4.8 2.45 2.35 3.9 4.65 4.35L22 9l-2.45 4.8c-2.55 2.9-5.95 4.25-10.15 3.85L5.8 20l1.35-3.25-3.65.8 2.65-2.45a16 16 0 0 1-3.8-2.85Z"
            fill="currentColor"
            stroke="none"
          />
          <path d="M8.15 14.9c2.35-.25 4.15-1.55 5.4-3.9" stroke="var(--color-fundo, #111)" strokeWidth="1.15" />
          <path d="M5.2 6.4 3.8 4.2M9.1 4.9V2.5M13 5.3l1.35-2.25" />
        </svg>
      )
    case 'NOV':
      return (
        <svg {...common}>
          <circle cx="12" cy="9.8" r="6.5" strokeDasharray=".01 2.55" strokeWidth="2.25" />
          <circle cx="12" cy="9.8" r="2.05" />
          <path d="M12 16.3v5.2M9.9 18.6h4.2M12 18.6v3.4" />
          <path d="M12 8.6V11M10.8 9.8h2.4" />
        </svg>
      )
    case 'VIACR':
      return (
        <svg {...common}>
          <path d="M12 2v16M8 6h8" />
          <path d="M3 21.5c2.5-2.7 5.5-4 9-4s6.5 1.3 9 4" />
          <circle cx="5.1" cy="14" r=".8" fill="currentColor" stroke="none" />
          <circle cx="19" cy="13" r=".8" fill="currentColor" stroke="none" />
          <circle cx="6.8" cy="17.7" r=".8" fill="currentColor" stroke="none" />
        </svg>
      )
    case 'SEQ':
      return (
        <svg {...common}>
          <path d="M9.5 18V5.5L19 4v11.5M9.5 8.8 19 7.3" />
          <ellipse cx="6.8" cy="18" rx="2.7" ry="2" />
          <ellipse cx="16.3" cy="15.5" rx="2.7" ry="2" />
          <path d="M3.5 5.5h3M5 4v3" />
        </svg>
      )
    case 'DOUT':
      return (
        <svg {...common}>
          <path d="M2.5 6c3.15-.85 6.05-.25 8.7 1.8v13c-2.65-2.05-5.55-2.65-8.7-1.8V6Z" />
          <path d="M21.5 6c-3.15-.85-6.05-.25-8.7 1.8v13c2.65-2.05 5.55-2.65 8.7-1.8V6Z" />
          <path d="M18.6 2.5c-3.9 2.1-5.9 5.15-5.9 9.1 1.9-.85 3.3-2.05 4.2-3.65M16.1 8.25l2.6.15" />
        </svg>
      )
    case 'DIARIA':
      return (
        <svg {...common}>
          <path d="M3 19h18M5 16h14" />
          <path d="M7 16a5 5 0 0 1 10 0" />
          <path d="M12 2.5v3M4.8 7.2 7 9.4M19.2 7.2 17 9.4M3 12h3M18 12h3" />
          <path d="M12 10v5M10.2 12h3.6" />
        </svg>
      )
    case 'BIBLIA':
      return (
        <svg {...common}>
          <path d="M2.5 5.3c3.5-.9 6.5-.25 9 1.9v13.5c-2.5-2.15-5.5-2.8-9-1.9V5.3Z" />
          <path d="M21.5 5.3c-3.5-.9-6.5-.25-9 1.9v13.5c2.5-2.15 5.5-2.8 9-1.9V5.3Z" />
          <path d="M17.5 8.3v6M15.3 10.5h4.4" />
        </svg>
      )
    case 'BASE':
      return (
        <svg {...common}>
          <path d="M11.8 2.5c-1 .5-1.55 1.55-1.7 3.1L9.3 12 7.2 7c-.45-1.05-2.05-.55-1.75.6l2 8.05L11.8 20" />
          <path d="M12.2 2.5c1 .5 1.55 1.55 1.7 3.1l.8 6.4 2.1-5c.45-1.05 2.05-.55 1.75.6l-2 8.05L12.2 20" />
          <path d="M12 3v17M8.2 16.3 5 19.5 8.8 22l3.2-2 3.2 2 3.8-2.5-3.2-3.2" />
        </svg>
      )
    case 'SANTOS':
      return (
        <svg {...common}>
          <ellipse cx="12" cy="4.4" rx="4.2" ry="1.55" />
          <circle cx="12" cy="9" r="2.7" />
          <path d="M6.1 20.5c.35-5.3 2.3-8 5.9-8s5.55 2.7 5.9 8" />
          <path d="m3.2 13.7 1.15 1.2 1.65-.3-.8 1.45.8 1.5-1.65-.3-1.15 1.2-.2-1.65-1.5-.75 1.5-.7.2-1.65Z" />
        </svg>
      )
    case 'SANTAS':
      return (
        <svg {...common}>
          <ellipse cx="12" cy="4.1" rx="4.1" ry="1.45" />
          <circle cx="12" cy="8.6" r="2.55" />
          <path d="M8.5 9.5c-2 2.7-2.85 6.4-2.65 11h12.3c.2-4.6-.65-8.3-2.65-11" />
          <path d="M9.2 14.6c.95.85 1.9 1.3 2.8 1.3s1.85-.45 2.8-1.3M12 15.9v4.6" />
        </svg>
      )
    default:
      return (
        <svg {...common}>
          <path d="M12 2v17M8 6h8M6 21h12" />
        </svg>
      )
  }
}
