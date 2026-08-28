'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const tabs = [
  {
    href: '/apresentacao',
    label: 'Início',
    icon: (active: boolean) => (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={active ? 2 : 1.5}
        className="w-6 h-6"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"
        />
      </svg>
    ),
  },
  {
    href: '/biblioteca',
    label: 'Biblioteca',
    icon: (active: boolean) => (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={active ? 2 : 1.5}
        className="w-6 h-6"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M2.25 12.75V12A2.25 2.25 0 0 1 4.5 9.75h15A2.25 2.25 0 0 1 21.75 12v.75m-8.69-6.44-2.12-2.12a1.5 1.5 0 0 0-1.061-.44H4.5A2.25 2.25 0 0 0 2.25 6v8.25m9.75-4.5v-.75A2.25 2.25 0 0 1 14.25 7.5h1.5a2.25 2.25 0 0 1 2.25 2.25V12m-9-3.75h9"
        />
      </svg>
    ),
  },
  {
    href: '/verificador',
    label: 'Verificador',
    icon: (active: boolean) => (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={active ? 2 : 1.5}
        className="w-6 h-6"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
        />
      </svg>
    ),
  },
  {
    href: '/santos',
    label: 'Santos',
    icon: (active: boolean) => (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={active ? 2 : 1.5}
        className="w-6 h-6"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z"
        />
      </svg>
    ),
  },
  {
    href: '/oracoes',
    label: 'Orações',
    icon: (active: boolean) => (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={active ? 2 : 1.5}
        className="w-6 h-6"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 21s7-4.35 7-11.25A4.75 4.75 0 0 0 14.25 5 4.73 4.73 0 0 0 12 5.57 4.73 4.73 0 0 0 9.75 5 4.75 4.75 0 0 0 5 9.75C5 16.65 12 21 12 21Z"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 5.57V3m-2 2h4"
        />
      </svg>
    ),
  },
  {
    href: '/perfil',
    label: 'Perfil',
    icon: (active: boolean) => (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={active ? 2 : 1.5}
        className="w-5 h-5 sm:w-6 sm:h-6"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M15.75 7.5a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.5 20.25a7.5 7.5 0 0 1 15 0"
        />
      </svg>
    ),
  },
]

export default function BottomNav() {
  const pathname = usePathname()

  return (
    <nav
      className="vf-bottom-nav fixed inset-x-0 bottom-0 z-50 border-t border-dourado/15 bg-fundo-card/95 backdrop-blur-xl"
      aria-label="Navegação principal"
    >
      <div className="vf-bottom-nav__inner grid grid-cols-6 items-stretch">
        {tabs.map((tab) => {
          const active = pathname === tab.href || pathname.startsWith(`${tab.href}/`)
          return (
            <Link
              key={tab.href}
              href={tab.href}
              prefetch
              aria-current={active ? 'page' : undefined}
              className={`vf-bottom-nav__link${active ? ' vf-bottom-nav__link--active' : ''} flex min-h-14 min-w-0 flex-col items-center justify-center gap-1 px-0.5 py-2 text-[10px] transition-colors sm:min-h-16 sm:text-xs ${
                active
                  ? 'text-dourado'
                  : 'text-texto-terciario hover:text-texto-secundario'
              }`}
            >
              <span className="vf-bottom-nav__icon" aria-hidden="true">
                {tab.icon(active)}
              </span>
              <span className={`max-w-full truncate px-0.5 ${active ? 'font-medium' : ''}`}>
                {tab.label}
              </span>
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
