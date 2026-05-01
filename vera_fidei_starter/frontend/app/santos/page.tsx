import BrandHeader from '@/components/BrandHeader'

const fathers = [
  { name: 'São Cipriano de Cartago', century: 'Séc. III', collection: 'PL 4' },
  { name: 'Santo Agostinho de Hipona', century: 'Séc. IV–V', collection: 'PL 32–46' },
  { name: 'São João Crisóstomo', century: 'Séc. IV', collection: 'PG 47–64' },
  { name: 'São Jerônimo', century: 'Séc. IV', collection: 'PL 22–30' },
  { name: 'São Ambrósio de Milão', century: 'Séc. IV', collection: 'PL 14–17' },
  { name: 'São Leão Magno', century: 'Séc. V', collection: 'PL 54–56' },
  { name: 'São Gregório Magno', century: 'Séc. VI', collection: 'PL 75–79' },
  { name: 'São Tomás de Aquino', century: 'Séc. XIII', collection: '—' },
]

export default function SantosPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 pt-8 pb-4">
      <BrandHeader
        title="Santos"
        description="Hagiologia católica, Padres da Igreja e Doutores."
      />

      {/* Coming soon banner */}
      <div className="mb-6 flex items-center gap-3 rounded-lg border border-dourado/20 bg-dourado/5 px-4 py-3">
        <svg
          viewBox="0 0 20 20"
          fill="currentColor"
          className="w-4 h-4 shrink-0 text-dourado"
        >
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-7-4a1 1 0 1 1-2 0 1 1 0 0 1 2 0ZM9 9a.75.75 0 0 0 0 1.5h.253a.25.25 0 0 1 .244.304l-.459 2.066A1.75 1.75 0 0 0 10.747 15H11a.75.75 0 0 0 0-1.5h-.253a.25.25 0 0 1-.244-.304l.459-2.066A1.75 1.75 0 0 0 9.253 9H9Z"
            clipRule="evenodd"
          />
        </svg>
        <p className="text-xs text-texto-secundario">
          Seção em desenvolvimento. Em breve: martirológio diário, santo do
          dia com acesso às obras na Biblioteca.
        </p>
      </div>

      {/* Static list of Church Fathers */}
      <div className="space-y-2">
        {fathers.map((father) => (
          <div
            key={father.name}
            className="flex items-center justify-between rounded-lg border border-fundo-borda bg-fundo-card px-4 py-3"
          >
            <div>
              <p className="text-sm font-medium text-texto">{father.name}</p>
              <p className="text-xs text-texto-terciario">{father.century}</p>
            </div>
            <span className="font-mono text-xs text-texto-terciario">
              {father.collection}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
