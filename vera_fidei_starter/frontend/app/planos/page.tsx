'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { getUser, type UserInfo } from '@/lib/auth'

interface Plano {
  key: string
  nome: string
  preco: string
  periodicidade: string
  limite: string
  indicado: string
  destaque?: boolean
  recursos: string[]
}

const PLAN_ORDER = ['fiel', 'catequista', 'apologeta', 'patristico', 'magisterio']

const PLANOS: Plano[] = [
  {
    key: 'fiel',
    nome: 'Fiel',
    preco: 'Grátis',
    periodicidade: '',
    limite: '10 verificações/mês',
    indicado: 'Consulta pessoal',
    recursos: [
      'Verificação de citações patrísticas',
      'Veredito com nível de confiança',
      'Histórico das últimas verificações',
      'Acesso à biblioteca digital',
    ],
  },
  {
    key: 'catequista',
    nome: 'Catequista',
    preco: 'R$ 9,90',
    periodicidade: '/mês',
    limite: '25 verificações/mês',
    indicado: 'Aulas e grupos',
    recursos: [
      'Tudo do plano Fiel',
      'Exportação de laudos em PDF',
      'Referência exata da fonte',
      'Histórico completo por conta',
    ],
  },
  {
    key: 'apologeta',
    nome: 'Apologeta',
    preco: 'R$ 29,99',
    periodicidade: '/mês',
    limite: '50 verificações/mês',
    indicado: 'Pesquisa e defesa da fé',
    destaque: true,
    recursos: [
      'Tudo do plano Catequista',
      'Contexto patrístico completo',
      'Análise de tradução e edição',
      'Acesso a PDFs digitalizados',
      'Exportação do histórico em CSV',
    ],
  },
  {
    key: 'patristico',
    nome: 'Patrístico',
    preco: 'R$ 59,99',
    periodicidade: '/mês',
    limite: '100 verificações/mês',
    indicado: 'Instituições pequenas',
    recursos: [
      'Tudo do plano Apologeta',
      'Painel de gestão institucional',
      'Convite e gestão de membros',
      'Relatório mensal de uso',
    ],
  },
  {
    key: 'magisterio',
    nome: 'Magistério',
    preco: 'R$ 99,99',
    periodicidade: '/mês',
    limite: 'Ilimitado',
    indicado: 'Integrações e equipes',
    recursos: [
      'Tudo do plano Patrístico',
      'API Key dedicada',
      'Endpoint REST /v1/verificar',
      'Geração e revogação de chaves',
      'Integração com sistemas externos',
    ],
  },
]

const PLAN_LABELS = Object.fromEntries(PLANOS.map((plano) => [plano.key, plano.nome]))

function planRank(plan: string | undefined) {
  return PLAN_ORDER.indexOf(plan ?? 'fiel')
}

export default function PlanosPage() {
  const [user, setUser] = useState<UserInfo | null>(null)

  useEffect(() => {
    getUser().then(setUser).catch(() => setUser(null))
  }, [])

  const planoAtual = useMemo(
    () => PLANOS.find((plano) => plano.key === user?.plan) ?? PLANOS[0],
    [user?.plan],
  )

  const currentRank = planRank(user?.plan)

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 sm:py-10">
      <section className="grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.6fr)] lg:items-end">
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-[0.22em] text-texto-terciario">
            Assinatura Vera.Fidei
          </p>
          <h1 className="font-eb-garamond text-3xl text-dourado sm:text-4xl">
            Planos para verificar, estudar e documentar fontes católicas.
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-texto-secundario">
            Escolha o nível de acesso conforme o uso: consulta pessoal, catequese,
            pesquisa patrística, instituições ou integrações via API.
          </p>
        </div>

        <div className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
          <p className="text-xs text-texto-terciario">Plano atual</p>
          <div className="mt-1 flex items-end justify-between gap-3">
            <span className="font-eb-garamond text-2xl text-dourado">
              {user ? PLAN_LABELS[user.plan] ?? user.plan : 'Visitante'}
            </span>
            <Link
              href={user ? '/perfil' : '/login?redirect=/planos'}
              className="rounded-md border border-dourado/40 px-3 py-2 text-xs font-medium text-dourado transition-colors hover:bg-dourado hover:text-fundo"
            >
              {user ? 'Ver perfil' : 'Entrar'}
            </Link>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-texto-terciario">
            {user
              ? `${planoAtual.limite} liberadas neste nível.`
              : 'Entre para ver seu plano ativo e avaliar upgrades.'}
          </p>
        </div>
      </section>

      <section className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {PLANOS.map((plano) => {
          const isAtual = user?.plan === plano.key
          const isUpgrade = user ? planRank(plano.key) > currentRank : plano.key !== 'fiel'
          const ctaHref = user ? '/perfil' : plano.key === 'fiel' ? '/cadastro' : '/login?redirect=/planos'

          return (
            <article
              key={plano.key}
              className={`relative flex min-h-[25rem] flex-col rounded-lg border p-4 transition-colors ${
                isAtual
                  ? 'border-dourado bg-dourado/8 shadow-[0_0_28px_rgba(201,168,76,0.12)]'
                  : plano.destaque
                    ? 'border-dourado/45 bg-fundo-card'
                    : 'border-fundo-borda bg-fundo-card'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-texto-terciario">
                    {plano.indicado}
                  </p>
                  <h2 className="mt-2 font-eb-garamond text-2xl text-texto">
                    {plano.nome}
                  </h2>
                </div>
                {(isAtual || plano.destaque) && (
                  <span
                    className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${
                      isAtual
                        ? 'bg-dourado text-fundo'
                        : 'border border-dourado/30 text-dourado'
                    }`}
                  >
                    {isAtual ? 'Atual' : 'Popular'}
                  </span>
                )}
              </div>

              <div className="mt-5 border-b border-fundo-borda pb-4">
                <div className="flex items-end gap-1">
                  <span className="font-eb-garamond text-3xl font-semibold text-dourado">
                    {plano.preco}
                  </span>
                  {plano.periodicidade && (
                    <span className="mb-1 text-xs text-texto-terciario">
                      {plano.periodicidade}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-xs text-texto-terciario">{plano.limite}</p>
              </div>

              <ul className="mt-4 flex flex-1 flex-col gap-2.5">
                {plano.recursos.map((recurso) => (
                  <li key={recurso} className="flex items-start gap-2 text-xs leading-relaxed text-texto-secundario">
                    <svg
                      viewBox="0 0 16 16"
                      fill="none"
                      className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-dourado"
                      aria-hidden="true"
                    >
                      <path
                        d="M3 8l3.5 3.5L13 4.5"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    <span>{recurso}</span>
                  </li>
                ))}
              </ul>

              <Link
                href={ctaHref}
                className={`mt-5 rounded-md px-3 py-2.5 text-center text-xs font-medium transition-colors ${
                  isAtual
                    ? 'border border-dourado/40 text-dourado hover:bg-dourado hover:text-fundo'
                    : plano.destaque || isUpgrade
                      ? 'bg-dourado text-fundo hover:bg-dourado-claro'
                      : 'border border-fundo-borda text-texto-secundario hover:border-dourado hover:text-dourado'
                }`}
              >
                {isAtual ? 'Gerenciar no perfil' : user ? 'Avaliar upgrade' : plano.key === 'fiel' ? 'Criar conta' : 'Entrar para avaliar'}
              </Link>
            </article>
          )
        })}
      </section>

      <section className="mt-8 rounded-lg border border-fundo-borda bg-fundo-card p-4 sm:p-5">
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-texto-terciario">
              Regras comerciais
            </p>
            <h2 className="mt-2 font-eb-garamond text-xl text-texto">
              Upgrade sem surpresa
            </h2>
          </div>
          <p className="text-xs leading-relaxed text-texto-terciario sm:col-span-2">
            Os limites e recursos já estão refletidos no app. A cobrança/checkout ainda
            depende de integração externa, então o perfil concentra a avaliação do plano
            atual, favoritos e recursos liberados.
          </p>
        </div>
      </section>
    </div>
  )
}
