import BrandHeader from '@/components/BrandHeader'

export default function OracoesLoading() {
  return (
    <div className="mx-auto max-w-3xl px-4 pt-8 pb-4">
      <BrandHeader
        title="Orações"
        description="Roteiros de oração, devoções tradicionais e espiritualidade ligada às fontes da Biblioteca."
      />
      <section className="mb-5 border-y border-fundo-borda py-3">
        <div className="h-7 w-36 animate-pulse rounded bg-fundo-card" />
        <div className="mt-3 h-4 w-64 max-w-full animate-pulse rounded bg-fundo-card" />
      </section>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {Array.from({ length: 8 }).map((_, index) => (
          <div
            key={index}
            className="rounded-lg border border-fundo-borda bg-fundo-card px-3 py-3"
          >
            <div className="h-4 w-44 max-w-full animate-pulse rounded bg-fundo" />
            <div className="mt-2 h-3 w-full animate-pulse rounded bg-fundo" />
          </div>
        ))}
      </div>
    </div>
  )
}
