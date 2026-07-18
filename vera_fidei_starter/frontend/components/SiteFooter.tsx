import Link from 'next/link'

const footerLinks = [
  { href: '/apresentacao', label: 'Início' },
  { href: '/planos', label: 'Planos' },
  { href: '/termos', label: 'Termos' },
  { href: '/privacidade', label: 'Privacidade' },
  { href: '/contato', label: 'Contato' },
]

export default function SiteFooter() {
  const year = new Date().getFullYear()

  return (
    <footer className="mx-auto w-full max-w-5xl px-4 pb-24 pt-10 text-center">
      <div className="border-t border-fundo-borda pt-5">
        <nav className="mb-4 flex flex-wrap justify-center gap-x-4 gap-y-2">
          {footerLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-xs font-medium text-texto-terciario transition-colors hover:text-dourado"
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <p className="text-xs leading-relaxed text-texto-terciario">
          © {year} Vera.Fidei. Aplicativo, biblioteca digital e sistema de
          verificação criados e desenvolvidos por{' '}
          <span className="font-medium text-texto-secundario">Mateus Cirineo</span>.
        </p>
        <p className="mt-1 text-xs leading-relaxed text-texto-terciario">
          Projeto católico independente para estudo, consulta de fontes e
          verificação de citações.
        </p>
      </div>
    </footer>
  )
}
