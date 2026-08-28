interface PrayerCategoryIconProps {
  code: string
  className?: string
}

/**
 * Small, code-native devotional symbols for the prayer catalogue.
 *
 * They deliberately use the same line weight and currentColor contract as the
 * rest of the Vera.Fidei icon system, while giving every category a distinct
 * Catholic symbol that remains recognizable inside the smallest medallion.
 */
export default function PrayerCategoryIcon({
  code,
  className = '',
}: PrayerCategoryIconProps) {
  const common = {
    viewBox: '0 0 32 32',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.6,
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
          <path d="M12.5 7.2 16 3.8l3.5 3.4" />
          <circle cx="16" cy="9.3" r="3.1" />
          <path d="M11.4 11.2c-2.8 3.4-4 8.6-4 14.8h17.2c0-6.2-1.2-11.4-4-14.8" />
          <path d="M12.1 17.5c1.3 1.1 2.6 1.7 3.9 1.7s2.6-.6 3.9-1.7M16 19.2V26" />
        </svg>
      )
    case 'DIV':
      return (
        <svg {...common}>
          <path d="M16 4v19M11.5 9h9" />
          <path d="M8.5 27h15M10.5 23h11" />
          <path d="M6.5 11.5 4 14l2.5 2.5M25.5 11.5 28 14l-2.5 2.5" />
        </svg>
      )
    case 'JOSE':
      return (
        <svg {...common}>
          <path d="M12 28V12" />
          <path d="M12 13C7.8 12.3 5.6 9.6 6.4 6c3.1.3 5 1.9 5.6 4.8C12.6 7.9 14.5 6.3 17.6 6c.8 3.6-1.4 6.3-5.6 7Z" />
          <path d="M12 20c-2.8-.2-4.8-1.3-6-3.2M12 23c2.8-.2 4.8-1.3 6-3.2" />
          <path d="M21 11v15h5M21 21h5" />
        </svg>
      )
    case 'EUCA':
      return (
        <svg {...common}>
          <circle cx="16" cy="7.5" r="4.2" />
          <path d="M16 5.3v4.4M13.8 7.5h4.4" />
          <path d="M9.5 13h13l-1.3 6a5.3 5.3 0 0 1-10.4 0l-1.3-6Z" />
          <path d="M16 24.3V28M11.8 28h8.4" />
        </svg>
      )
    case 'ESP':
      return (
        <svg {...common}>
          <path d="M4 17c6.6 1.4 10-.7 11.6-7 1 3.1 2.8 5 5.8 5.7L28 13l-3.2 6.1c-3.2 3.6-7.4 5.3-12.4 5.1" />
          <path d="m5 22 7.4-2.2L8 27" />
          <path d="M7 7 5.5 4.5M12 5.5 12 2M17 6l1.7-3" />
        </svg>
      )
    case 'NOV':
      return (
        <svg {...common}>
          <circle cx="16" cy="13.5" r="8.5" strokeDasharray=".1 3.5" strokeWidth="2.6" />
          <path d="M16 22v6M13.5 25h5M16 25v5" />
          <circle cx="16" cy="13.5" r="3" />
          <path d="M14.3 13.5h3.4M16 11.8v3.4" />
        </svg>
      )
    case 'VIACR':
      return (
        <svg {...common}>
          <path d="M16 3v21M10.5 8.5h11" />
          <path d="M4 28c3.4-3.2 7.4-4.8 12-4.8S24.6 24.8 28 28" />
          <path d="M6.5 18h5M9 15.5v5M22 17h4M24 15v4" />
        </svg>
      )
    case 'SEQ':
      return (
        <svg {...common}>
          <path d="M13 23V7l12-2v15" />
          <path d="M13 11 25 9" />
          <ellipse cx="9.5" cy="23" rx="3.5" ry="2.7" />
          <ellipse cx="21.5" cy="20" rx="3.5" ry="2.7" />
          <path d="M5 6h4M7 4v4" />
        </svg>
      )
    case 'DOUT':
      return (
        <svg {...common}>
          <path d="M4 8c3.8-1 7.5-.3 11 2v17c-3.5-2.3-7.2-3-11-2V8Z" />
          <path d="M28 8c-3.8-1-7.5-.3-11 2v17c3.5-2.3 7.2-3 11-2V8Z" />
          <path d="M23.5 3.5c-5 2.5-7.6 6.3-7.6 11.4 2.5-1.3 4.3-3 5.4-5.2M20.2 9.9l3.2.2" />
        </svg>
      )
    case 'DIARIA':
      return (
        <svg {...common}>
          <path d="M4 24h24M6 20h20" />
          <path d="M9 20a7 7 0 0 1 14 0" />
          <path d="M16 4v4M6.8 8.2l2.8 2.8M25.2 8.2 22.4 11M4 15h4M24 15h4" />
          <path d="M16 12v6M13.5 14.5h5" />
        </svg>
      )
    case 'BIBLIA':
      return (
        <svg {...common}>
          <path d="M3.5 6.5c4.5-1.2 8.3-.4 11.5 2.3V27c-3.2-2.7-7-3.5-11.5-2.3V6.5Z" />
          <path d="M28.5 6.5c-4.5-1.2-8.3-.4-11.5 2.3V27c3.2-2.7 7-3.5 11.5-2.3V6.5Z" />
          <path d="M23 10v8M20 13h6" />
        </svg>
      )
    case 'BASE':
      return (
        <svg {...common}>
          <path d="m13.8 28-5-14.4a2.7 2.7 0 0 1 2.5-3.6h.2L16 21l4.5-11h.2a2.7 2.7 0 0 1 2.5 3.6L18.2 28" />
          <path d="M11.5 10V5.5a2.3 2.3 0 0 1 4.5-.7V14M20.5 10V5.5a2.3 2.3 0 0 0-4.5-.7V14M9 28h14" />
          <path d="M16 2v3M13.5 3.5h5" />
        </svg>
      )
    case 'SANTOS':
      return (
        <svg {...common}>
          <ellipse cx="16" cy="6" rx="5" ry="2.3" />
          <circle cx="16" cy="11.5" r="3.5" />
          <path d="M8.5 27c.5-6 3-9 7.5-9s7 3 7.5 9M5 19.5l2 1.1-.4 2.3 1.7-1.6 2.1 1.1-1-2.1 1.7-1.6-2.3.3-1-2.1-.5 2.3L5 19.5Z" />
        </svg>
      )
    case 'SANTAS':
      return (
        <svg {...common}>
          <ellipse cx="16" cy="5.5" rx="5" ry="2.2" />
          <circle cx="16" cy="11" r="3.2" />
          <path d="M11.7 12.5C9 16 7.8 21 8 27h16c.2-6-1-11-3.7-14.5" />
          <path d="M12.2 19.5c1.3 1 2.6 1.5 3.8 1.5s2.5-.5 3.8-1.5M16 21v6" />
        </svg>
      )
    default:
      return (
        <svg {...common}>
          <path d="M16 3v23M10 9h12M7 28h18" />
        </svg>
      )
  }
}
