import Image from 'next/image'
import Link from 'next/link'
import PwaInstallButton from '@/components/PwaInstallButton'
import IconMedallion from '@/components/ui/IconMedallion'
import SectionHeading from '@/components/ui/SectionHeading'
import SurfaceCard from '@/components/ui/SurfaceCard'

type IconName =
  | 'book'
  | 'database'
  | 'device'
  | 'external'
  | 'instagram'
  | 'search'
  | 'shield'
  | 'tiktok'
  | 'warning'
  | 'youtube'

const socialLinks: { label: string; value: string; href: string; icon: IconName }[] = [
  {
    label: 'TikTok',
    value: '@mattcirineo, o católico',
    href: 'https://www.tiktok.com/@mattcirineo.catolico',
    icon: 'tiktok',
  },
  {
    label: 'Instagram',
    value: '@vera.fidei',
    href: 'https://www.instagram.com/vera.fidei',
    icon: 'instagram',
  },
  {
    label: 'YouTube',
    value: '@mattcirineo',
    href: 'https://www.youtube.com/@mattcirineo',
    icon: 'youtube',
  },
]

const coverHighlights: { label: string; icon: IconName; image: string }[] = [
  {
    label: 'Fontes primárias',
    icon: 'book',
    image: '/branding/presentation-primary-sources.webp',
  },
  {
    label: 'Tradição católica',
    icon: 'database',
    image: '/branding/presentation-tradition.webp',
  },
  {
    label: 'Verificação de citações',
    icon: 'shield',
    image: '/branding/presentation-verification.webp',
  },
]

const presentationFeatures: { title: string; desc: string; icon: IconName }[] = [
  {
    title: 'Busca lexical',
    desc: 'O sistema utiliza mecanismos de busca textual para encontrar correspondências exatas ou próximas, respeitando as características do latim, do grego patrístico e de outras línguas presentes nas coleções como PL, PG e PO.',
    icon: 'search',
  },
  {
    title: 'Busca semântica',
    desc: 'Além da busca direta, o Vera.Fidei identifica passagens equivalentes em significado, mesmo quando há traduções, variações editoriais ou diferenças entre edições das coleções patrísticas e documentos do Magistério.',
    icon: 'book',
  },
  {
    title: 'Classificação determinística',
    desc: 'O resultado não depende de interpretações subjetivas. A análise é feita por critérios objetivos, garantindo consistência, rastreabilidade e fidelidade às fontes.',
    icon: 'shield',
  },
  {
    title: 'Proveniência completa',
    desc: 'Cada resultado apresenta coleção (PL, PG, PO, Magistério, Concílios), volume, coluna, edição, idioma e permite acesso direto ao trecho correspondente no documento original, incluindo bulas, encíclicas e demais registros oficiais.',
    icon: 'database',
  },
]

const collectionItems = [
  { label: 'Patrologia Latina', code: 'PL', desc: 'textos em latim dos Padres da Igreja' },
  { label: 'Patrologia Grega', code: 'PG', desc: 'textos patrísticos em grego' },
  { label: 'Patrologia Orientalis', code: 'PO', desc: 'textos orientais em diversas línguas antigas' },
  { label: 'Concílios', code: 'CONC', desc: 'documentos conciliares ecumênicos e regionais' },
  { label: 'Magistério', code: 'MAG', desc: 'encíclicas, constituições apostólicas, bulas papais e outros documentos oficiais' },
]

const planItems = [
  { nome: 'Fiel', preco: 'Grátis', desc: '10 verificações/mês · 5 buscas/dia compartilhadas' },
  { nome: 'Catequista', preco: 'R$ 9,90/mês', desc: '25 verificações/mês · 20 buscas/dia compartilhadas · Laudos em PDF' },
  { nome: 'Apologeta', preco: 'R$ 29,99/mês', desc: '50 verificações/mês · 50 buscas/dia compartilhadas · PDFs digitalizados', destaque: true },
  { nome: 'Patrístico', preco: 'R$ 59,99/mês', desc: '100 verificações/mês · 100 buscas/dia compartilhadas · PDFs digitalizados e painel institucional' },
  { nome: 'Magistério', preco: 'R$ 99,99/mês', desc: 'Tudo ilimitado · PDFs digitalizados · API dedicada' },
]

function LineIcon({ name, className = 'h-5 w-5' }: { name: IconName; className?: string }) {
  const common = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.6,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    className,
    'aria-hidden': true,
  }

  switch (name) {
    case 'book':
      return (
        <svg {...common}>
          <path d="M4 5.5A3.5 3.5 0 0 1 7.5 2H11v17H7.5A3.5 3.5 0 0 0 4 22V5.5Z" />
          <path d="M20 5.5A3.5 3.5 0 0 0 16.5 2H13v17h3.5A3.5 3.5 0 0 1 20 22V5.5Z" />
        </svg>
      )
    case 'database':
      return (
        <svg {...common}>
          <ellipse cx="12" cy="5" rx="7.5" ry="3" />
          <path d="M4.5 5v7c0 1.66 3.36 3 7.5 3s7.5-1.34 7.5-3V5" />
          <path d="M4.5 12v7c0 1.66 3.36 3 7.5 3s7.5-1.34 7.5-3v-7" />
        </svg>
      )
    case 'device':
      return (
        <svg {...common}>
          <rect x="6" y="2" width="12" height="20" rx="2.5" />
          <path d="M10 18.5h4" />
        </svg>
      )
    case 'external':
      return (
        <svg {...common}>
          <path d="M5 12h13" />
          <path d="m14 8 4 4-4 4" />
        </svg>
      )
    case 'instagram':
      return (
        <svg {...common}>
          <rect x="3" y="3" width="18" height="18" rx="5" />
          <circle cx="12" cy="12" r="4" />
          <circle cx="17.5" cy="6.5" r=".75" fill="currentColor" stroke="none" />
        </svg>
      )
    case 'search':
      return (
        <svg {...common}>
          <circle cx="10.5" cy="10.5" r="6.5" />
          <path d="m15.5 15.5 4.5 4.5" />
        </svg>
      )
    case 'shield':
      return (
        <svg {...common}>
          <path d="M12 2.5 20 6v5.5c0 5-3.4 8.25-8 10-4.6-1.75-8-5-8-10V6l8-3.5Z" />
          <path d="m8.5 12 2.25 2.25 4.75-5" />
        </svg>
      )
    case 'tiktok':
      return (
        <svg {...common}>
          <path d="M14 4v10.5a4.5 4.5 0 1 1-4.5-4.5" />
          <path d="M14 4c.75 2.25 2.25 3.75 4.5 4" />
        </svg>
      )
    case 'warning':
      return (
        <svg {...common}>
          <path d="M10.3 3.8 2.5 18a2 2 0 0 0 1.75 3h15.5a2 2 0 0 0 1.75-3L13.7 3.8a2 2 0 0 0-3.4 0Z" />
          <path d="M12 9v4" />
          <path d="M12 17h.01" />
        </svg>
      )
    case 'youtube':
      return (
        <svg {...common}>
          <path d="M21 12c0 3.2-.4 5.25-1.2 6.05C19 18.85 16.4 19 12 19s-7-.15-7.8-.95C3.4 17.25 3 15.2 3 12s.4-5.25 1.2-6.05C5 5.15 7.6 5 12 5s7 .15 7.8.95C20.6 6.75 21 8.8 21 12Z" />
          <path d="m10 9 5 3-5 3V9Z" />
        </svg>
      )
  }
}

function PresentationCover() {
  return (
    <SurfaceCard
      tone="gold"
      className="relative overflow-hidden p-0 text-left shadow-[0_24px_80px_rgba(0,0,0,0.48)]"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_12%,rgba(201,168,76,0.18),transparent_34%),radial-gradient(circle_at_100%_40%,rgba(92,26,26,0.38),transparent_42%)]"
      />

      <div className="relative border-b border-dourado/20 bg-[linear-gradient(160deg,rgba(61,16,16,0.78),rgba(17,17,17,0.5)_68%)] px-5 py-7 text-center sm:px-7 sm:py-9">
        <Image
          src="/branding/Logo-VF-seal.png"
          alt="Vera.Fidei Catolico"
          width={192}
          height={192}
          className="mx-auto h-auto w-28 drop-shadow-[0_10px_22px_rgba(0,0,0,0.55)] sm:w-32"
          priority
        />

        <p className="mt-3 font-garamond text-lg font-medium text-dourado">
          MattCirineo
        </p>
        <h1 className="mt-1 font-garamond text-5xl font-semibold tracking-tight text-texto sm:text-6xl">
          Vera.Fidei
        </h1>
        <p className="mx-auto mt-2 max-w-md font-garamond text-xl italic leading-snug text-dourado-claro sm:text-2xl">
          Biblioteca Católica Digital com Fontes Primárias e Verificação de Citações
        </p>
      </div>

      <div className="relative space-y-5 px-4 py-5 sm:px-6 sm:py-6">
        <blockquote className="border-l-2 border-dourado pl-4 font-garamond text-xl italic leading-relaxed text-texto">
          Eucharistia via mea ad Caelum est
        </blockquote>

        <div className="grid gap-2">
          {socialLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              target="_blank"
              rel="noreferrer"
              className="group flex min-h-14 items-center gap-3 rounded-lg border border-dourado/15 bg-fundo/75 px-3 py-2.5 transition-[border-color,background-color,transform] hover:-translate-y-0.5 hover:border-dourado/40 hover:bg-vinho-escuro/20 focus-visible:border-dourado/50"
            >
              <IconMedallion size="sm">
                <LineIcon name={link.icon} className="h-4 w-4" />
              </IconMedallion>
              <span className="min-w-0 flex-1">
                <span className="block text-[10px] font-medium uppercase tracking-[0.12em] text-dourado">
                  {link.label}
                </span>
                <span className="block truncate text-sm font-medium text-texto-secundario">
                  {link.value}
                </span>
              </span>
              <LineIcon
                name="external"
                className="h-4 w-4 shrink-0 text-dourado/70 transition-transform group-hover:translate-x-0.5"
              />
            </a>
          ))}
        </div>

        <div className="grid gap-2 sm:grid-cols-3">
          {coverHighlights.map((item) => (
            <div
              key={item.label}
              className="group relative isolate flex min-h-24 items-center overflow-hidden rounded-lg border border-dourado/20 px-3 py-3 shadow-[inset_0_0_30px_rgba(0,0,0,0.3)] sm:min-h-28"
            >
              <Image
                src={item.image}
                alt=""
                fill
                sizes="(max-width: 639px) 100vw, 33vw"
                className="-z-20 object-cover object-right transition-transform duration-500 group-hover:scale-[1.03]"
              />
              <div className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,rgba(7,8,8,0.98)_0%,rgba(7,8,8,0.9)_42%,rgba(7,8,8,0.32)_78%,rgba(7,8,8,0.18)_100%)]" />
              <div className="relative z-10 flex max-w-[74%] items-center gap-3 sm:max-w-full sm:flex-col sm:items-start sm:text-left">
                <IconMedallion size="sm">
                  <LineIcon name={item.icon} className="h-4 w-4" />
                </IconMedallion>
                <p className="text-xs font-medium text-dourado drop-shadow-[0_1px_5px_rgba(0,0,0,0.95)]">
                  {item.label}
                </p>
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-center pt-1">
          <Image
            src="/branding/Logo-VF-wine.png"
            alt="Selo Vera.Fidei vinho"
            width={96}
            height={96}
            className="h-12 w-12 rounded-full border border-dourado/20 opacity-85 shadow-[0_8px_28px_rgba(0,0,0,0.35)]"
          />
        </div>
      </div>
    </SurfaceCard>
  )
}

export default function ApresentacaoPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-14 px-4 pb-5 pt-14 sm:px-6 lg:space-y-20">
      {/* Hero */}
      <section className="grid items-start gap-7 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)] lg:gap-10">
        <PresentationCover />

        <div className="space-y-5 lg:sticky lg:top-8 lg:pt-4">
          <h2 className="max-w-2xl font-garamond text-3xl font-medium leading-[1.08] text-texto sm:text-4xl lg:text-5xl">
            Uma biblioteca católica digital pensada para quem busca estudar, compreender e defender a fé com base em fontes autênticas.
          </h2>

          <div className="space-y-3">
            <SurfaceCard className="flex gap-3 p-4">
              <IconMedallion className="mt-0.5 shrink-0">
                <LineIcon name="book" />
              </IconMedallion>
              <p className="text-sm leading-relaxed text-texto-secundario">
                O Vera.Fidei reúne, em um único ambiente, obras patrísticas, documentos do Magistério e coleções clássicas da tradição da Igreja, organizadas de forma clara, acessível e fiel às edições originais.
              </p>
            </SurfaceCard>

            <SurfaceCard className="flex gap-3 p-4">
              <IconMedallion className="mt-0.5 shrink-0">
                <LineIcon name="device" />
              </IconMedallion>
              <p className="text-sm leading-relaxed text-texto-secundario">
                Projetado para uso em dispositivos móveis e também em ambiente web, o sistema permite consultar rapidamente textos, aprofundar estudos e acompanhar referências diretamente nas fontes.
              </p>
            </SurfaceCard>

            <SurfaceCard tone="gold" className="flex gap-3 p-4">
              <IconMedallion className="mt-0.5 shrink-0">
                <LineIcon name="shield" />
              </IconMedallion>
              <p className="text-sm leading-relaxed text-texto-secundario">
                Além disso, integra um mecanismo de verificação de citações que confronta textos atribuídos aos Padres da Igreja com os documentos originais, auxiliando na identificação de erros, distorções ou citações fora de contexto — especialmente útil em estudos teológicos, debates e produção de conteúdo.
              </p>
            </SurfaceCard>
          </div>

          <div className="flex flex-col gap-3 pt-1 sm:flex-row">
            <Link
              href="/cadastro"
              className="inline-flex min-h-12 flex-1 items-center justify-center gap-2 rounded-lg bg-dourado px-6 py-3 text-sm font-semibold text-fundo shadow-[0_10px_30px_rgba(201,168,76,0.16)] transition-[background-color,transform] hover:-translate-y-0.5 hover:bg-dourado-claro"
            >
              Criar conta grátis
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path fillRule="evenodd" d="M3 10a.75.75 0 0 1 .75-.75h10.638L10.23 5.29a.75.75 0 1 1 1.04-1.08l5.5 5.25a.75.75 0 0 1 0 1.08l-5.5 5.25a.75.75 0 1 1-1.04-1.08l4.158-3.96H3.75A.75.75 0 0 1 3 10Z" clipRule="evenodd" />
              </svg>
            </Link>
            <Link
              href="/login"
              className="inline-flex min-h-12 flex-1 items-center justify-center rounded-lg border border-dourado/30 bg-fundo-card/70 px-6 py-3 text-sm font-medium text-texto-secundario transition-[border-color,color,transform] hover:-translate-y-0.5 hover:border-dourado/55 hover:text-dourado"
            >
              Já tenho conta — Entrar
            </Link>
          </div>
          <PwaInstallButton />
        </div>
      </section>

      {/* O que é */}
      <section className="grid gap-5 border-y border-fundo-borda py-8 md:grid-cols-[minmax(0,0.7fr)_minmax(0,1.3fr)] md:gap-10 md:py-10">
        <SectionHeading as="h2">O que é o Vera.Fidei</SectionHeading>
        <div className="space-y-3">
          <p className="font-garamond text-xl leading-relaxed text-texto sm:text-2xl">
            O Vera.Fidei é uma biblioteca digital católica com foco na preservação, organização e acesso às fontes primárias da tradição da Igreja.
          </p>
          <p className="text-sm leading-relaxed text-texto-secundario">
            Seu acervo é composto por obras clássicas como a Patrologia Latina (PL), a Patrologia Grega (PG) e a Patrologia Orientalis (PO), além de documentos do Magistério, concílios ecumênicos e regionais, bulas papais, encíclicas e outros textos fundamentais da tradição católica.
          </p>
          <p className="text-sm leading-relaxed text-texto-secundario">
            A proposta da plataforma é oferecer não apenas acesso ao conteúdo, mas também segurança na informação, permitindo que cada citação seja rastreada até sua origem com precisão.
          </p>
        </div>
      </section>

      {/* Como funciona */}
      <section className="space-y-5">
        <SectionHeading as="h2">Como funciona</SectionHeading>
        <div className="grid gap-3 md:grid-cols-2">
          {presentationFeatures.map(({ title, desc, icon }) => (
            <SurfaceCard key={title} className="flex gap-4 p-4 sm:p-5">
              <IconMedallion className="shrink-0">
                <LineIcon name={icon} />
              </IconMedallion>
              <div>
                <p className="font-garamond text-xl font-medium leading-tight text-texto">
                  {title}
                </p>
                <p className="mt-1.5 text-sm leading-relaxed text-texto-secundario">
                  {desc}
                </p>
              </div>
            </SurfaceCard>
          ))}
        </div>
      </section>

      {/* Diferencial */}
      <section className="space-y-5">
        <SectionHeading as="h2">O problema que resolve</SectionHeading>
        <div className="grid gap-3 md:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
          <SurfaceCard tone="wine" className="flex gap-4 p-5 sm:p-6">
            <IconMedallion tone="wine" className="shrink-0">
              <LineIcon name="warning" />
            </IconMedallion>
            <div className="space-y-3">
              <p className="font-garamond text-xl font-medium leading-snug text-texto">
                A circulação de citações incorretas, incompletas ou inexistentes é cada vez mais comum, especialmente em conteúdos digitais e até mesmo em materiais produzidos por inteligências artificiais.
              </p>
              <p className="text-sm leading-relaxed text-texto-secundario">
                O Vera.Fidei responde a esse problema oferecendo um meio confiável de verificação, permitindo confrontar qualquer citação com o texto original e identificar sua autenticidade, localização e contexto.
              </p>
            </div>
          </SurfaceCard>

          <SurfaceCard tone="gold" className="flex gap-4 p-5 sm:p-6">
            <IconMedallion className="shrink-0">
              <LineIcon name="shield" />
            </IconMedallion>
            <p className="text-sm leading-relaxed text-texto-secundario">
              O sistema prioriza sempre a fonte primária — o texto original na língua em que foi escrito — utilizando traduções apenas como apoio.
            </p>
          </SurfaceCard>
        </div>
      </section>

      {/* Acervo */}
      <section className="space-y-5">
        <SectionHeading as="h2">Acervo</SectionHeading>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {collectionItems.map(({ label, code, desc }) => (
            <SurfaceCard key={code} className="flex min-h-full flex-col p-3.5 sm:p-4">
              <IconMedallion size="md" className="mb-3">
                <span className="font-garamond text-sm font-semibold">{code}</span>
              </IconMedallion>
              <p className="font-garamond text-lg font-medium leading-tight text-texto">
                {label}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-texto-terciario">{desc}</p>
            </SurfaceCard>
          ))}
        </div>

        <SurfaceCard tone="gold" className="flex gap-4 p-4 sm:p-5">
          <IconMedallion className="shrink-0">
            <LineIcon name="book" />
          </IconMedallion>
          <p className="text-sm leading-relaxed text-texto-secundario">
            Cada obra pode conter múltiplas edições, traduções e arquivos digitais, sempre vinculados entre si, permitindo consulta precisa e acesso direto ao trecho correspondente dentro do documento original.
          </p>
        </SurfaceCard>
      </section>

      <div className="border-t border-fundo-borda" />

      {/* Planos resumidos */}
      <section className="space-y-5">
        <SectionHeading as="h2">Planos</SectionHeading>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {planItems.map(({ nome, preco, desc, destaque }) => (
            <SurfaceCard
              key={nome}
              tone={destaque ? 'gold' : 'default'}
              className="p-4"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2 lg:block">
                <p className={`font-garamond text-lg font-medium ${destaque ? 'text-dourado' : 'text-texto'}`}>
                  {nome}
                </p>
                <p className="text-sm font-semibold text-dourado lg:mt-1">{preco}</p>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-texto-terciario">{desc}</p>
            </SurfaceCard>
          ))}
        </div>
        <p className="text-center text-xs leading-relaxed text-texto-terciario">
          A cota diária de buscas é única e compartilhada entre a Biblioteca (Citações dos
          Padres), a Catena Patrum e os Catecismos.
        </p>
        <div className="flex flex-col items-center gap-3 pt-2 sm:flex-row sm:justify-center">
          <Link
            href="/cadastro"
            className="rounded-lg bg-dourado px-6 py-3 text-sm font-semibold text-fundo transition-colors hover:bg-dourado-claro"
          >
            Começar com o plano Fiel — grátis
          </Link>
          <Link
            href="/planos"
            className="text-xs text-texto-terciario underline-offset-2 hover:text-dourado hover:underline"
          >
            Ver todos os planos e recursos
          </Link>
        </div>
      </section>
    </div>
  )
}
