import BrandHeader from '@/components/BrandHeader'
import SurfaceCard from '@/components/ui/SurfaceCard'

export default function OracoesLoading() {
  return (
    <div className="mx-auto max-w-3xl px-4 pt-8 pb-4">
      <BrandHeader
        title="Orações"
        description="Roteiros de oração, devoções tradicionais e espiritualidade ligada às fontes da Biblioteca."
      />
      <div aria-hidden="true">
        <section className="mb-5 space-y-4 border-y border-fundo-borda py-5">
          <div>
            <div className="h-7 w-36 animate-pulse rounded bg-fundo-card motion-reduce:animate-none" />
            <div className="mt-3 h-4 w-72 max-w-full animate-pulse rounded bg-fundo-card motion-reduce:animate-none" />
            <div className="mt-2 h-3 w-56 max-w-full animate-pulse rounded bg-fundo-card motion-reduce:animate-none" />
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            {Array.from({ length: 2 }).map((_, index) => (
              <SurfaceCard key={index} tone="gold" className="p-0">
                <div className="flex min-h-24 items-center gap-3 px-3 py-3.5 sm:px-4">
                  <div className="h-[2.875rem] w-[2.875rem] shrink-0 animate-pulse rounded-full border border-dourado/20 bg-dourado/10 motion-reduce:animate-none" />
                  <div className="min-w-0 flex-1">
                    <div className="h-7 w-16 animate-pulse rounded bg-fundo/80 motion-reduce:animate-none" />
                    <div className="mt-2 h-3 w-14 animate-pulse rounded bg-fundo/80 motion-reduce:animate-none" />
                  </div>
                </div>
              </SurfaceCard>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div
                key={index}
                className="flex min-h-11 items-center justify-center gap-2 rounded-lg border border-dourado/15 bg-fundo/80 px-3 py-2"
              >
                <div className="h-4 w-4 animate-pulse rounded-full bg-dourado/15 motion-reduce:animate-none" />
                <div className="h-3 w-24 animate-pulse rounded bg-fundo-card motion-reduce:animate-none" />
              </div>
            ))}
          </div>
        </section>

        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          {Array.from({ length: 8 }).map((_, index) => (
            <SurfaceCard key={index} className="p-0">
              <div className="flex min-h-[76px] items-center gap-3 px-3 py-2.5 sm:px-4">
                <div className="h-[2.875rem] w-[2.875rem] shrink-0 animate-pulse rounded-full border border-dourado/15 bg-dourado/10 motion-reduce:animate-none" />
                <div className="min-w-0 flex-1">
                  <div className="h-5 w-40 max-w-full animate-pulse rounded bg-fundo motion-reduce:animate-none" />
                  <div className="mt-2 h-3 w-full animate-pulse rounded bg-fundo motion-reduce:animate-none" />
                </div>
                <div className="h-7 w-10 shrink-0 animate-pulse rounded-full bg-fundo motion-reduce:animate-none" />
                <div className="h-4 w-2 shrink-0 animate-pulse rounded bg-dourado/15 motion-reduce:animate-none" />
              </div>
            </SurfaceCard>
          ))}
        </div>
      </div>
    </div>
  )
}
