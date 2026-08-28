'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  createCheckoutSession,
  getUser,
  openBillingPortal,
  type UserInfo,
} from '@/lib/auth'

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
    indicado: 'Uso pessoal',
    recursos: [
      'Verificação básica de citações',
      'Resultado com nível de confiança',
      'Histórico recente de verificações',
      'Biblioteca completa, incluindo a leitura dos PDFs digitalizados',
      '5 buscas/dia entre Biblioteca, Catena e Catecismos — cota compartilhada',
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
      'Laudos em PDF',
      'Referência exata da fonte',
      'Histórico completo da conta',
      'Biblioteca completa, incluindo a leitura dos PDFs digitalizados',
      '20 buscas/dia entre Biblioteca, Catena e Catecismos — cota compartilhada',
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
      'Contexto patrístico mais completo',
      'Análise de tradução e variação textual',
      'Exportação do histórico em Excel',
      '50 buscas/dia entre Biblioteca, Catena e Catecismos — cota compartilhada',
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
      '100 buscas/dia entre Biblioteca, Catena e Catecismos — cota compartilhada',
    ],
  },
  {
    key: 'magisterio',
    nome: 'Magistério',
    preco: 'R$ 99,99',
    periodicidade: '/mês',
    limite: 'Ilimitado',
    indicado: 'Equipes e integrações',
    recursos: [
      'Tudo do plano Patrístico',
      'API dedicada',
      'Endpoint REST /v1/verificar',
      'Geração e revogação de chaves',
      'Integração com sistemas externos',
      'Acesso ilimitado aos recursos do plano',
      'Buscas ilimitadas na Biblioteca, Catena e Catecismos',
    ],
  },
]

const PLAN_LABELS = Object.fromEntries(PLANOS.map((plano) => [plano.key, plano.nome]))
const ACTIVE_BILLING_STATUSES = new Set(['active', 'trialing'])

function planRank(plan: string | undefined) {
  const index = PLAN_ORDER.indexOf(plan ?? 'fiel')
  return index >= 0 ? index : 0
}

function isOwner(user: UserInfo | null) {
  return user?.billing_status === 'owner' || user?.email.toLowerCase() === 'mateuscirineo@gmail.com'
}

export default function PlanosPage() {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [busyPlan, setBusyPlan] = useState('')
  const [billingError, setBillingError] = useState('')
  const [couponCode, setCouponCode] = useState('')
  const [couponError, setCouponError] = useState('')

  useEffect(() => {
    getUser().then(setUser).catch(() => setUser(null))
  }, [])

  const planoAtual = useMemo(
    () => PLANOS.find((plano) => plano.key === user?.plan) ?? PLANOS[0],
    [user?.plan],
  )

  const currentRank = planRank(user?.plan)
  const owner = isOwner(user)
  const hasActiveBilling = Boolean(user?.billing_status && ACTIVE_BILLING_STATUSES.has(user.billing_status))

  async function handleSubscribe(plan: string) {
    setBillingError('')
    setCouponError('')
    setBusyPlan(plan)
    try {
      const { url } = await createCheckoutSession(plan, couponCode || undefined)
      window.location.assign(url)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erro ao iniciar assinatura.'
      if (msg.toLowerCase().includes('cupom')) {
        setCouponError(msg)
      } else {
        setBillingError(msg)
      }
    } finally {
      setBusyPlan('')
    }
  }

  async function handleManageBilling() {
    setBillingError('')
    setBusyPlan('portal')
    try {
      const { url } = await openBillingPortal()
      window.location.assign(url)
    } catch (err: unknown) {
      setBillingError(err instanceof Error ? err.message : 'Erro ao abrir assinatura.')
    } finally {
      setBusyPlan('')
    }
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 sm:py-10">
      <section className="grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.6fr)] lg:items-end">
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-[0.22em] text-texto-terciario">
            Assinatura Vera.Fidei
          </p>
          <h1 className="font-garamond text-3xl text-dourado sm:text-4xl">
            Planos mensais para verificar, estudar e documentar fontes católicas.
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-texto-secundario">
            Escolha o nível de acesso conforme o uso. As assinaturas pagas são mensais
            e podem ser canceladas a qualquer momento pelo portal seguro de cobrança.
            A cota diária é única e compartilhada entre a Biblioteca (Citações dos
            Padres), a Catena Patrum e os Catecismos.
          </p>
        </div>

        <div className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
          <p className="text-xs text-texto-terciario">Plano atual</p>
          <div className="mt-1 flex items-end justify-between gap-3">
            <span className="font-garamond text-2xl text-dourado">
              {user ? PLAN_LABELS[user.plan] ?? user.plan : 'Visitante'}
            </span>
            {user && hasActiveBilling && !owner ? (
              <button
                type="button"
                onClick={handleManageBilling}
                disabled={busyPlan === 'portal'}
                className="rounded-md border border-dourado/40 px-3 py-2 text-xs font-medium text-dourado transition-colors hover:bg-dourado hover:text-fundo disabled:cursor-default disabled:opacity-60"
              >
                Gerenciar
              </button>
            ) : user ? (
              <Link
                href="/perfil"
                className="rounded-md border border-dourado/40 px-3 py-2 text-xs font-medium text-dourado transition-colors hover:bg-dourado hover:text-fundo"
              >
                {owner ? 'Acesso total' : 'Ver perfil'}
              </Link>
            ) : (
              <Link
                href="/login?redirect=/planos"
                className="rounded-md border border-dourado/40 px-3 py-2 text-xs font-medium text-dourado transition-colors hover:bg-dourado hover:text-fundo"
              >
                Entrar
              </Link>
            )}
          </div>
          <p className="mt-2 text-xs leading-relaxed text-texto-terciario">
            {user
              ? owner
                ? 'Conta proprietária com todos os recursos liberados.'
                : `${planoAtual.limite} liberadas neste nível.`
              : 'Entre para ver seu plano ativo e assinar melhorias.'}
          </p>
        </div>
      </section>

      {billingError && (
        <div className="mt-5 rounded-lg border border-vermelho/40 bg-vermelho/10 p-3 text-sm text-vermelho">
          {billingError}
        </div>
      )}

      {user && !isOwner(user) && (
        <div className="mt-5 flex flex-col gap-1.5 sm:flex-row sm:items-center">
          <div className="flex max-w-sm flex-1 gap-2">
            <input
              type="text"
              value={couponCode}
              onChange={(e) => {
                setCouponCode(e.target.value.toUpperCase())
                setCouponError('')
              }}
              placeholder="Cupom de desconto (opcional)"
              maxLength={50}
              className="h-9 flex-1 rounded border border-fundo-borda bg-fundo-card px-3 text-sm text-texto placeholder:text-texto-terciario outline-none focus:border-dourado"
            />
          </div>
          {couponError ? (
            <p className="text-xs text-vermelho">{couponError}</p>
          ) : (
            <p className="text-xs text-texto-terciario">Será aplicado ao plano selecionado abaixo.</p>
          )}
        </div>
      )}

      <section className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {PLANOS.map((plano) => {
          const isAtual = user?.plan === plano.key
          const isUpgrade = user ? planRank(plano.key) > currentRank : plano.key !== 'fiel'
          const isPaid = plano.key !== 'fiel'
          const loading = busyPlan === plano.key

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
                  <h2 className="mt-2 font-garamond text-2xl text-texto">
                    {plano.nome}
                  </h2>
                </div>
                {(isAtual || plano.destaque) && (
                  <span
                    className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${
                      isAtual ? 'bg-dourado text-fundo' : 'border border-dourado/30 text-dourado'
                    }`}
                  >
                    {isAtual ? 'Atual' : 'Popular'}
                  </span>
                )}
              </div>

              <div className="mt-5 border-b border-fundo-borda pb-4">
                <div className="flex items-end gap-1">
                  <span className="font-garamond text-3xl font-semibold text-dourado">
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

              {!user ? (
                <Link
                  href={plano.key === 'fiel' ? '/cadastro' : '/login?redirect=/planos'}
                  className={`mt-5 rounded-md px-3 py-2.5 text-center text-xs font-medium transition-colors ${
                    plano.destaque || isUpgrade
                      ? 'bg-dourado text-fundo hover:bg-dourado-claro'
                      : 'border border-fundo-borda text-texto-secundario hover:border-dourado hover:text-dourado'
                  }`}
                >
                  {plano.key === 'fiel' ? 'Criar conta' : 'Entrar para assinar'}
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    if (owner || isAtual) {
                      if (hasActiveBilling && !owner) void handleManageBilling()
                      return
                    }
                    if (isPaid) void handleSubscribe(plano.key)
                  }}
                  disabled={owner || !isPaid || loading || (isAtual && !hasActiveBilling)}
                  className={`mt-5 rounded-md px-3 py-2.5 text-center text-xs font-medium transition-colors disabled:cursor-default disabled:opacity-60 ${
                    isAtual
                      ? 'border border-dourado/40 text-dourado hover:bg-dourado hover:text-fundo'
                      : plano.destaque || isUpgrade
                        ? 'bg-dourado text-fundo hover:bg-dourado-claro'
                        : 'border border-fundo-borda text-texto-secundario hover:border-dourado hover:text-dourado'
                  }`}
                >
                  {owner
                    ? 'Liberado'
                    : loading
                      ? 'Abrindo...'
                      : isAtual
                        ? hasActiveBilling
                          ? 'Gerenciar assinatura'
                          : 'Plano atual'
                        : isPaid
                          ? 'Assinar mensalmente'
                          : 'Plano gratuito'}
                </button>
              )}
            </article>
          )
        })}
      </section>

      <section className="mt-8 rounded-lg border border-fundo-borda bg-fundo-card p-4 sm:p-5">
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-texto-terciario">
              Cobrança
            </p>
            <h2 className="mt-2 font-garamond text-xl text-texto">
              Mensal e cancelável
            </h2>
          </div>
          <p className="text-xs leading-relaxed text-texto-terciario sm:col-span-2">
            O checkout cria uma assinatura mensal segura. O cancelamento e a troca de
            forma de pagamento ficam no portal de cobrança; quando o provedor confirma
            pagamento ou cancelamento por webhook, o plano da conta é atualizado.
          </p>
        </div>
      </section>
    </div>
  )
}
