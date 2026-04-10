import Link from 'next/link'

export default function ApresentacaoPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 pt-8 pb-4 space-y-10">
      {/* Hero */}
      <section className="text-center space-y-4 py-4">
        <h1 className="font-garamond text-5xl font-semibold tracking-tight text-texto">
          Vera.Fidei
        </h1>
        <p className="font-garamond text-xl text-dourado italic">
          Biblioteca Católica Digital com Fontes Primárias e Verificação de Citações
        </p>
        <p className="text-sm text-texto-secundario leading-relaxed max-w-sm mx-auto">
          Uma biblioteca católica digital pensada para quem busca estudar, compreender e defender a fé com base em fontes autênticas.
        </p>
        <p className="text-sm text-texto-secundario leading-relaxed max-w-sm mx-auto">
          O Vera.Fidei reúne, em um único ambiente, obras patrísticas, documentos do Magistério e coleções clássicas da tradição da Igreja, organizadas de forma clara, acessível e fiel às edições originais.
        </p>
        <p className="text-sm text-texto-secundario leading-relaxed max-w-sm mx-auto">
          Projetado para uso em dispositivos móveis e também em ambiente web, o sistema permite consultar rapidamente textos, aprofundar estudos e acompanhar referências diretamente nas fontes.
        </p>
        <p className="text-sm text-texto-secundario leading-relaxed max-w-sm mx-auto">
          Além disso, integra um mecanismo de verificação de citações que confronta textos atribuídos aos Padres da Igreja com os documentos originais, auxiliando na identificação de erros, distorções ou citações fora de contexto — especialmente útil em estudos teológicos, debates e produção de conteúdo.
        </p>
        <Link
          href="/biblioteca"
          className="inline-flex items-center gap-2 rounded-lg bg-vinho px-5 py-2.5 text-sm font-semibold text-texto transition-colors hover:bg-vinho-claro"
        >
          Explorar biblioteca
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
            <path
              fillRule="evenodd"
              d="M3 10a.75.75 0 0 1 .75-.75h10.638L10.23 5.29a.75.75 0 1 1 1.04-1.08l5.5 5.25a.75.75 0 0 1 0 1.08l-5.5 5.25a.75.75 0 1 1-1.04-1.08l4.158-3.96H3.75A.75.75 0 0 1 3 10Z"
              clipRule="evenodd"
            />
          </svg>
        </Link>
      </section>

      <div className="border-t border-fundo-borda" />

      {/* O que é */}
      <section className="space-y-3">
        <h2 className="font-garamond text-2xl font-medium text-texto">
          O que é o Vera.Fidei
        </h2>
        <p className="text-sm text-texto-secundario leading-relaxed">
          O Vera.Fidei é uma biblioteca digital católica com foco na preservação, organização e acesso às fontes primárias da tradição da Igreja.
        </p>
        <p className="text-sm text-texto-secundario leading-relaxed">
          Seu acervo é composto por obras clássicas como a Patrologia Latina (PL), a Patrologia Grega (PG) e a Patrologia Orientalis (PO), além de documentos do Magistério, concílios ecumênicos e regionais, bulas papais, encíclicas e outros textos fundamentais da tradição católica.
        </p>
        <p className="text-sm text-texto-secundario leading-relaxed">
          A proposta da plataforma é oferecer não apenas acesso ao conteúdo, mas também segurança na informação, permitindo que cada citação seja rastreada até sua origem com precisão.
        </p>
      </section>

      {/* Como funciona */}
      <section className="space-y-3">
        <h2 className="font-garamond text-2xl font-medium text-texto">
          Como funciona
        </h2>
        <div className="space-y-3">
          {[
            {
              title: 'Busca lexical',
              desc: 'O sistema utiliza mecanismos de busca textual para encontrar correspondências exatas ou próximas, respeitando as características do latim, do grego patrístico e de outras línguas presentes nas coleções como PL, PG e PO.',
            },
            {
              title: 'Busca semântica',
              desc: 'Além da busca direta, o Vera.Fidei identifica passagens equivalentes em significado, mesmo quando há traduções, variações editoriais ou diferenças entre edições das coleções patrísticas e documentos do Magistério.',
            },
            {
              title: 'Classificação determinística',
              desc: 'O resultado não depende de interpretações subjetivas. A análise é feita por critérios objetivos, garantindo consistência, rastreabilidade e fidelidade às fontes.',
            },
            {
              title: 'Proveniência completa',
              desc: 'Cada resultado apresenta coleção (PL, PG, PO, Magistério, Concílios), volume, coluna, edição, idioma e permite acesso direto ao trecho correspondente no documento original, incluindo bulas, encíclicas e demais registros oficiais.',
            },
          ].map(({ title, desc }) => (
            <div
              key={title}
              className="flex gap-3 rounded-lg border border-fundo-borda bg-fundo-card p-4"
            >
              <span className="mt-0.5 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-dourado mt-2" />
              <div>
                <p className="text-sm font-medium text-texto">{title}</p>
                <p className="text-sm text-texto-secundario leading-relaxed mt-0.5">
                  {desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Diferencial */}
      <section className="space-y-3">
        <h2 className="font-garamond text-2xl font-medium text-texto">
          O problema que resolve
        </h2>
        <div className="rounded-lg border border-vinho/40 bg-vinho-escuro/20 p-4 space-y-2">
          <p className="text-sm font-medium text-texto">
            A circulação de citações incorretas, incompletas ou inexistentes é cada vez mais comum, especialmente em conteúdos digitais e até mesmo em materiais produzidos por inteligências artificiais.
          </p>
          <p className="text-sm text-texto-secundario leading-relaxed">
            O Vera.Fidei responde a esse problema oferecendo um meio confiável de verificação, permitindo confrontar qualquer citação com o texto original e identificar sua autenticidade, localização e contexto.
          </p>
        </div>
        <p className="text-sm text-texto-secundario leading-relaxed">
          O sistema prioriza sempre a fonte primária — o texto original na língua em que foi escrito — utilizando traduções apenas como apoio.
        </p>
      </section>

      {/* Acervo */}
      <section className="space-y-3">
        <h2 className="font-garamond text-2xl font-medium text-texto">
          Acervo
        </h2>
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: 'Patrologia Latina', code: 'PL', desc: 'textos em latim dos Padres da Igreja' },
            { label: 'Patrologia Grega', code: 'PG', desc: 'textos patrísticos em grego' },
            { label: 'Patrologia Orientalis', code: 'PO', desc: 'textos orientais em diversas línguas antigas' },
            { label: 'Concílios', code: 'CONC', desc: 'documentos conciliares ecumênicos e regionais' },
            { label: 'Magistério', code: 'MAG', desc: 'encíclicas, constituições apostólicas, bulas papais e outros documentos oficiais' },
          ].map(({ label, code, desc }) => (
            <div
              key={code}
              className="rounded-lg border border-fundo-borda bg-fundo-card p-3"
            >
              <p className="font-mono text-xs text-dourado mb-0.5">{code}</p>
              <p className="text-sm font-medium text-texto">{label}</p>
              <p className="text-xs text-texto-terciario">{desc}</p>
            </div>
          ))}
        </div>
        <p className="text-sm text-texto-secundario leading-relaxed">
          Cada obra pode conter múltiplas edições, traduções e arquivos digitais, sempre vinculados entre si, permitindo consulta precisa e acesso direto ao trecho correspondente dentro do documento original.
        </p>
      </section>
    </div>
  )
}
