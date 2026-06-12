export default function SiteFooter() {
  const year = new Date().getFullYear()

  return (
    <footer className="mx-auto w-full max-w-2xl px-4 pb-24 pt-8 text-center">
      <div className="border-t border-fundo-borda pt-4">
        <p className="text-xs leading-relaxed text-texto-terciario">
          © {year} Vera.Fidei. Aplicativo, biblioteca digital e sistema de verificação criados e desenvolvidos por{' '}
          <span className="font-medium text-texto-secundario">Mateus Cirineo</span>.
        </p>
        <p className="mt-1 text-xs leading-relaxed text-texto-terciario">
          Projeto católico independente para estudo, consulta de fontes e verificação de citações.
        </p>
      </div>
    </footer>
  )
}
