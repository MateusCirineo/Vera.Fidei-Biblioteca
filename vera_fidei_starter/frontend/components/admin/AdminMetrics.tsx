'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import {
  getAdminAccounts,
  getAdminMetrics,
  grantAdminPlan,
  revokeAdminPlan,
  type AdminAccountsPageResponse,
  type AdminMetricCount,
  type AdminMetricsResponse,
} from '@/lib/api'

const GIFT_PLAN_OPTIONS = [
  { value: 'catequista', label: 'Catequista' },
  { value: 'apologeta', label: 'Apologeta' },
  { value: 'patristico', label: 'Patrístico' },
  { value: 'magisterio', label: 'Magistério' },
]

const GIFT_DURATION_OPTIONS = [
  { value: '1', label: '1 mês' },
  { value: '3', label: '3 meses' },
  { value: '12', label: '12 meses' },
  { value: '', label: 'Permanente' },
]

const DEFAULT_REFRESH_MS = 15_000
const ANALYTICS_TIME_ZONE = 'America/Sao_Paulo'
const ANALYTICS_TIME_ZONE_LABEL = 'horário de Brasília'

function number(value: number) {
  return value.toLocaleString('pt-BR')
}

function dateTime(value?: string | null) {
  if (!value) return 'Ainda sem acessos registrados'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return 'Data indisponível'
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'medium',
    timeZone: ANALYTICS_TIME_ZONE,
  }).format(parsed)
}

function shortDate(value: string) {
  const parsed = new Date(`${value}T12:00:00Z`)
  return new Intl.DateTimeFormat('pt-BR', {
    weekday: 'short',
    day: '2-digit',
    timeZone: ANALYTICS_TIME_ZONE,
  }).format(parsed)
}

export default function AdminMetrics() {
  const [data, setData] = useState<AdminMetricsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [accountsTab, setAccountsTab] = useState<'recent' | 'all'>('recent')
  const requestInFlight = useRef(false)

  const load = useCallback(async (initial = false) => {
    if (requestInFlight.current) return
    requestInFlight.current = true
    if (initial) setLoading(true)
    else setRefreshing(true)
    try {
      const result = await getAdminMetrics()
      setData(result)
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível carregar as métricas.')
    } finally {
      requestInFlight.current = false
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    void load(true)
    const timer = window.setInterval(() => {
      if (active && document.visibilityState === 'visible') void load(false)
    }, (data?.refresh_after_seconds ?? 15) * 1000 || DEFAULT_REFRESH_MS)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [data?.refresh_after_seconds, load])

  const dailyMaximum = useMemo(
    () => Math.max(1, ...(data?.daily_activity.map((item) => item.page_views) ?? [1])),
    [data?.daily_activity],
  )

  if (loading && !data) {
    return (
      <div className="rounded-lg border border-fundo-borda bg-fundo-card px-4 py-12 text-center text-sm text-texto-terciario">
        Carregando métricas em tempo real...
      </div>
    )
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-emerald-400">
            <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
            Tempo real
          </div>
          <h2 className="mt-1 font-eb-garamond text-2xl text-texto">Visão geral do Vera Fidei</h2>
          <p className="mt-1 text-sm text-texto-terciario">
            Atualização automática a cada {data?.refresh_after_seconds ?? 15} segundos. Todos os períodos usam o {ANALYTICS_TIME_ZONE_LABEL}.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <p className="text-xs text-texto-terciario">
            {data ? `Atualizado em ${dateTime(data.generated_at)}` : ''}
          </p>
          <button
            type="button"
            onClick={() => load(false)}
            disabled={refreshing}
            className="h-9 rounded-md border border-fundo-borda px-3 text-xs text-texto-secundario transition-colors hover:border-dourado/60 hover:text-dourado disabled:opacity-50"
          >
            {refreshing ? 'Atualizando...' : 'Atualizar agora'}
          </button>
        </div>
      </div>

      {error && (
        <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}

      {data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Contas criadas" value={data.accounts_total} detail={`${number(data.registrations.today)} hoje`} />
            <MetricCard label="Contas gratuitas" value={data.accounts_free} detail="Plano Fiel" />
            <MetricCard label="Assinantes ativos" value={data.subscribers_active} detail={`${data.conversion_rate.toLocaleString('pt-BR')}% das contas`} accent />
            <MetricCard label="Online agora" value={data.visitors_online_now} detail="Últimos 5 minutos" live />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="Contas e assinaturas" subtitle="Contagens exatas do banco de usuários">
              <div className="grid grid-cols-2 gap-3">
                <SmallMetric label="Ativas" value={data.accounts_active} />
                <SmallMetric label="Desativadas" value={data.accounts_disabled} />
                <SmallMetric label="Cancelando" value={data.subscribers_canceling} />
                <SmallMetric label="Pagamento pendente" value={data.subscriptions_pending} />
              </div>
              <PeriodMetrics
                title="Novos cadastros"
                rows={[{ label: 'Contas criadas', period: data.registrations }]}
              />
              <MetricRows rows={data.plans} empty="Nenhum plano encontrado." />
            </Panel>

            <Panel
              title="Acessos"
              subtitle={`Medição desta base iniciada em ${dateTime(data.tracking_started_at)} (${ANALYTICS_TIME_ZONE_LABEL})`}
            >
              <SmallMetric label="Visitantes únicos desde o início desta medição" value={data.visitors_unique_total} />
              <PeriodMetrics
                rows={[
                  { label: 'Visitantes únicos', period: data.visitors },
                  { label: 'Visualizações de páginas', period: data.page_views },
                ]}
              />
              <p className="mt-4 text-xs leading-5 text-texto-terciario">
                “Hoje” começa à meia-noite no {ANALYTICS_TIME_ZONE_LABEL}. Os períodos de 7 e 30 dias incluem hoje.
                “Visitante único” significa um navegador reconhecido pelo cookie próprio do Vera Fidei. Nenhum IP ou identificação pessoal é guardado nessa medição.
              </p>
            </Panel>
          </div>

          <Panel title="Atividade dos últimos 7 dias" subtitle="Visualizações, visitantes e novas contas por dia">
            <div className="grid h-56 grid-cols-7 items-end gap-2 sm:gap-4">
              {data.daily_activity.map((item) => (
                <div key={item.date} className="flex h-full min-w-0 flex-col justify-end">
                  <div className="mb-2 text-center text-[10px] text-texto-terciario sm:text-xs">
                    {number(item.page_views)}
                  </div>
                  <div className="flex h-36 items-end justify-center gap-1">
                    <div
                      title={`${item.page_views} visualizações`}
                      className="w-3 min-h-1 rounded-t bg-dourado sm:w-5"
                      style={{ height: `${Math.max(3, item.page_views / dailyMaximum * 100)}%` }}
                    />
                    <div
                      title={`${item.visitors} visitantes`}
                      className="w-3 min-h-1 rounded-t bg-emerald-500 sm:w-5"
                      style={{ height: `${Math.max(3, item.visitors / dailyMaximum * 100)}%` }}
                    />
                  </div>
                  <p className="mt-2 truncate text-center text-[10px] capitalize text-texto-terciario sm:text-xs">
                    {shortDate(item.date)}
                  </p>
                  <p className="truncate text-center text-[9px] text-texto-terciario/70">
                    +{item.registrations} contas
                  </p>
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-4 text-xs text-texto-terciario">
              <span className="flex items-center gap-2"><i className="h-2 w-2 rounded-full bg-dourado" />Visualizações</span>
              <span className="flex items-center gap-2"><i className="h-2 w-2 rounded-full bg-emerald-500" />Visitantes</span>
            </div>
          </Panel>

          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="Buscas e verificações" subtitle="Ações registradas pelas funções principais">
              <PeriodMetrics
                rows={[
                  { label: 'Pesquisas no acervo', period: data.searches },
                  { label: 'Verificações de citações', period: data.verifications },
                ]}
              />
              <h3 className="mt-5 text-xs font-semibold uppercase tracking-[0.18em] text-texto-terciario">Situação das assinaturas</h3>
              <MetricRows rows={data.subscription_statuses} empty="Nenhuma assinatura registrada." />
            </Panel>

            <Panel title="Páginas mais acessadas" subtitle="Últimos 7 dias">
              <MetricRows rows={data.top_pages_7_days} empty="Os acessos começarão a aparecer após a ativação da telemetria." />
            </Panel>
          </div>

          <Panel
            title="Contas"
            subtitle={
              accountsTab === 'recent'
                ? 'As 10 últimas contas, sem incluir a conta administrativa'
                : `Busque entre as ${number(data.accounts_total)} contas cadastradas`
            }
          >
            <GiftPlanForm />

            <div
              className="mt-5 grid grid-cols-2 gap-1 rounded-lg border border-fundo-borda bg-fundo p-1"
              role="tablist"
              aria-label="Contas"
            >
              <button
                id="admin-accounts-recent-tab"
                type="button"
                role="tab"
                aria-selected={accountsTab === 'recent'}
                aria-controls="admin-accounts-recent-panel"
                tabIndex={accountsTab === 'recent' ? 0 : -1}
                onClick={() => setAccountsTab('recent')}
                className={`min-h-11 rounded-md px-3 py-2 text-center text-xs font-semibold transition-colors sm:text-sm ${
                  accountsTab === 'recent'
                    ? 'bg-dourado text-fundo shadow-sm'
                    : 'text-texto-secundario hover:bg-fundo-card hover:text-dourado'
                }`}
              >
                Contas mais recentes
              </button>
              <button
                id="admin-accounts-all-tab"
                type="button"
                role="tab"
                aria-selected={accountsTab === 'all'}
                aria-controls="admin-accounts-all-panel"
                tabIndex={accountsTab === 'all' ? 0 : -1}
                onClick={() => setAccountsTab('all')}
                className={`min-h-11 rounded-md px-3 py-2 text-center text-xs font-semibold transition-colors sm:text-sm ${
                  accountsTab === 'all'
                    ? 'bg-dourado text-fundo shadow-sm'
                    : 'text-texto-secundario hover:bg-fundo-card hover:text-dourado'
                }`}
              >
                Todas as contas ({number(data.accounts_total)})
              </button>
            </div>

            {accountsTab === 'recent' && (
              <div id="admin-accounts-recent-panel" role="tabpanel" aria-labelledby="admin-accounts-recent-tab" className="mt-4">
                {data.recent_accounts.length === 0 ? (
                  <p className="py-6 text-center text-sm text-texto-terciario">Nenhuma conta criada.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[760px] text-left text-sm">
                      <thead className="border-b border-fundo-borda text-xs uppercase tracking-[0.14em] text-texto-terciario">
                        <tr>
                          <th className="px-3 py-3 font-medium">Pessoa</th>
                          <th className="px-3 py-3 font-medium">Plano</th>
                          <th className="px-3 py-3 font-medium">Situação</th>
                          <th className="px-3 py-3 font-medium">E-mail</th>
                          <th className="px-3 py-3 font-medium">Cadastro</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-fundo-borda">
                        {data.recent_accounts.map((account) => (
                          <tr key={account.id}>
                            <td className="px-3 py-3">
                              <p className="font-medium text-texto">{account.name}</p>
                              <p className="text-xs text-texto-terciario">{account.email}</p>
                            </td>
                            <td className="px-3 py-3 text-texto-secundario">{account.plan_label}</td>
                            <td className="px-3 py-3 text-texto-secundario">{account.billing_status ?? 'Gratuita'}</td>
                            <td className="px-3 py-3">
                              <StatusPill active={account.email_verified} yes="Verificado" no="Não verificado" />
                            </td>
                            <td className="px-3 py-3 text-texto-terciario">{dateTime(account.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {accountsTab === 'all' && (
              <div id="admin-accounts-all-panel" role="tabpanel" aria-labelledby="admin-accounts-all-tab">
                <AllAccountsBrowser />
              </div>
            )}
          </Panel>
        </>
      )}
    </section>
  )
}

function MetricCard({ label, value, detail, accent = false, live = false }: { label: string; value: number; detail: string; accent?: boolean; live?: boolean }) {
  return (
    <article className={`rounded-lg border bg-fundo-card p-4 ${accent ? 'border-dourado/50' : live ? 'border-emerald-500/40' : 'border-fundo-borda'}`}>
      <p className="text-xs uppercase tracking-[0.16em] text-texto-terciario">{label}</p>
      <p className={`mt-2 font-eb-garamond text-3xl ${live ? 'text-emerald-400' : 'text-dourado'}`}>{number(value)}</p>
      <p className="mt-1 text-xs text-texto-terciario">{detail}</p>
    </article>
  )
}

function SmallMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-fundo-borda bg-fundo/50 p-3">
      <p className="text-[11px] leading-4 text-texto-terciario">{label}</p>
      <p className="mt-1 font-eb-garamond text-2xl text-texto">{number(value)}</p>
    </div>
  )
}

function PeriodMetrics({
  title,
  rows,
}: {
  title?: string
  rows: Array<{ label: string; period: { today: number; last_7_days: number; last_30_days: number } }>
}) {
  return (
    <div className="mt-4 overflow-hidden rounded-md border border-fundo-borda">
      {title && (
        <h3 className="border-b border-fundo-borda bg-fundo/40 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-texto-terciario">
          {title}
        </h3>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] text-left text-sm">
          <thead className="border-b border-fundo-borda bg-fundo/20 text-[11px] text-texto-terciario">
            <tr>
              <th className="px-3 py-2 font-medium">Métrica</th>
              <th className="px-3 py-2 text-right font-medium">Hoje</th>
              <th className="px-3 py-2 text-right font-medium">Últimos 7 dias</th>
              <th className="px-3 py-2 text-right font-medium">Últimos 30 dias</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-fundo-borda">
            {rows.map((row) => (
              <tr key={row.label}>
                <th className="px-3 py-3 text-xs font-medium text-texto-secundario">{row.label}</th>
                <td className="px-3 py-3 text-right font-eb-garamond text-xl text-texto">{number(row.period.today)}</td>
                <td className="px-3 py-3 text-right font-eb-garamond text-xl text-texto">{number(row.period.last_7_days)}</td>
                <td className="px-3 py-3 text-right font-eb-garamond text-xl text-texto">{number(row.period.last_30_days)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Panel({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <article className="rounded-lg border border-fundo-borda bg-fundo-card p-4 sm:p-5">
      <h2 className="font-eb-garamond text-xl text-texto">{title}</h2>
      <p className="mt-1 text-xs text-texto-terciario">{subtitle}</p>
      <div className="mt-4">{children}</div>
    </article>
  )
}

function MetricRows({ rows, empty }: { rows: AdminMetricCount[]; empty: string }) {
  if (rows.length === 0) return <p className="py-5 text-center text-sm text-texto-terciario">{empty}</p>
  const maximum = Math.max(1, ...rows.map((row) => row.count))
  return (
    <div className="mt-4 space-y-3">
      {rows.map((row) => (
        <div key={row.key}>
          <div className="mb-1 flex items-center justify-between gap-3 text-xs">
            <span className="min-w-0 truncate text-texto-secundario">{row.label}</span>
            <span className="font-semibold text-texto">{number(row.count)}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-fundo-borda">
            <div className="h-full rounded-full bg-dourado" style={{ width: `${Math.max(2, row.count / maximum * 100)}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

function GiftPlanForm() {
  const [mode, setMode] = useState<'grant' | 'revoke'>('grant')
  const [email, setEmail] = useState('')
  const [plan, setPlan] = useState(GIFT_PLAN_OPTIONS[2]!.value)
  const [months, setMonths] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!email.trim()) return
    setSubmitting(true)
    setMessage(null)
    try {
      if (mode === 'grant') {
        const result = await grantAdminPlan({
          email: email.trim(),
          plan,
          months: months ? Number(months) : null,
        })
        const durationLabel = result.billing_current_period_end
          ? `até ${dateTime(result.billing_current_period_end)}`
          : 'sem data de expiração'
        setMessage({
          tone: 'success',
          text: `${result.email} agora está no plano ${result.plan_label} (${durationLabel}).`,
        })
      } else {
        const result = await revokeAdminPlan(email.trim())
        setMessage({
          tone: 'success',
          text: `Presente revogado. ${result.email} voltou ao plano ${result.plan_label}.`,
        })
      }
    } catch (err) {
      setMessage({
        tone: 'error',
        text: err instanceof Error ? err.message : 'Não foi possível concluir a operação.',
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded-md border border-dourado/30 bg-fundo/40 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-sm font-semibold text-texto">Conceder plano (presente)</h3>
          <p className="text-xs text-texto-terciario">
            Dá acesso a um plano pago sem passar pelo Stripe — útil para agradecer quem ajuda a divulgar.
          </p>
        </div>
        <div className="flex gap-1 rounded-md border border-fundo-borda bg-fundo p-1 text-xs">
          <button
            type="button"
            onClick={() => setMode('grant')}
            className={`rounded px-2 py-1 font-medium transition-colors ${
              mode === 'grant' ? 'bg-dourado text-fundo' : 'text-texto-secundario hover:text-dourado'
            }`}
          >
            Conceder
          </button>
          <button
            type="button"
            onClick={() => setMode('revoke')}
            className={`rounded px-2 py-1 font-medium transition-colors ${
              mode === 'revoke' ? 'bg-dourado text-fundo' : 'text-texto-secundario hover:text-dourado'
            }`}
          >
            Revogar
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end sm:flex-wrap">
        <label className="flex flex-col gap-1 text-xs text-texto-terciario sm:min-w-[220px] sm:flex-1">
          E-mail da conta
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="pessoa@exemplo.com"
            className="h-9 rounded-md border border-fundo-borda bg-fundo px-3 text-sm text-texto placeholder:text-texto-terciario"
          />
        </label>

        {mode === 'grant' && (
          <>
            <label className="flex flex-col gap-1 text-xs text-texto-terciario">
              Plano
              <select
                value={plan}
                onChange={(event) => setPlan(event.target.value)}
                className="h-9 rounded-md border border-fundo-borda bg-fundo px-2 text-sm text-texto"
              >
                {GIFT_PLAN_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1 text-xs text-texto-terciario">
              Duração
              <select
                value={months}
                onChange={(event) => setMonths(event.target.value)}
                className="h-9 rounded-md border border-fundo-borda bg-fundo px-2 text-sm text-texto"
              >
                {GIFT_DURATION_OPTIONS.map((option) => (
                  <option key={option.label} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="h-9 rounded-md bg-dourado px-4 text-xs font-semibold text-fundo transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {submitting ? 'Enviando...' : mode === 'grant' ? 'Conceder presente' : 'Revogar presente'}
        </button>
      </form>

      {message && (
        <p
          className={`mt-3 rounded-md border px-3 py-2 text-xs ${
            message.tone === 'success'
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
              : 'border-red-500/30 bg-red-500/10 text-red-300'
          }`}
        >
          {message.text}
        </p>
      )}
    </div>
  )
}

function AllAccountsBrowser() {
  const PAGE_SIZE = 20
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [data, setData] = useState<AdminAccountsPageResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [search])

  useEffect(() => {
    setPage(1)
  }, [debouncedSearch])

  useEffect(() => {
    let active = true
    setLoading(true)
    getAdminAccounts({ page, pageSize: PAGE_SIZE, search: debouncedSearch || undefined })
      .then((result) => {
        if (!active) return
        setData(result)
        setError('')
      })
      .catch((err) => {
        if (!active) return
        setError(err instanceof Error ? err.message : 'Não foi possível carregar as contas.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [page, debouncedSearch])

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  return (
    <div className="mt-4 space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <input
          type="text"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar por nome ou e-mail..."
          className="h-9 w-full rounded-md border border-fundo-borda bg-fundo px-3 text-sm text-texto placeholder:text-texto-terciario sm:max-w-xs"
        />
        {data && (
          <p className="text-xs text-texto-terciario">
            {number(data.total)} conta{data.total === 1 ? '' : 's'} no total
          </p>
        )}
      </div>

      {error && (
        <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-fundo-borda text-xs uppercase tracking-[0.14em] text-texto-terciario">
            <tr>
              <th className="px-3 py-3 font-medium">Pessoa</th>
              <th className="px-3 py-3 font-medium">Plano</th>
              <th className="px-3 py-3 font-medium">Situação</th>
              <th className="px-3 py-3 font-medium">E-mail</th>
              <th className="px-3 py-3 font-medium">Cadastro</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-fundo-borda">
            {(data?.accounts ?? []).map((account) => (
              <tr key={account.id}>
                <td className="px-3 py-3">
                  <p className="font-medium text-texto">{account.name}</p>
                  <p className="text-xs text-texto-terciario">{account.email}</p>
                </td>
                <td className="px-3 py-3 text-texto-secundario">{account.plan_label}</td>
                <td className="px-3 py-3 text-texto-secundario">{account.billing_status ?? 'Gratuita'}</td>
                <td className="px-3 py-3">
                  <StatusPill active={account.email_verified} yes="Verificado" no="Não verificado" />
                </td>
                <td className="px-3 py-3 text-texto-terciario">{dateTime(account.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && data && data.accounts.length === 0 && (
          <p className="py-6 text-center text-sm text-texto-terciario">Nenhuma conta encontrada.</p>
        )}
        {loading && <p className="py-6 text-center text-sm text-texto-terciario">Carregando...</p>}
      </div>

      <div className="flex items-center justify-between text-xs text-texto-terciario">
        <button
          type="button"
          onClick={() => setPage((current) => Math.max(1, current - 1))}
          disabled={page <= 1 || loading}
          className="h-8 rounded-md border border-fundo-borda px-3 disabled:opacity-40"
        >
          Anterior
        </button>
        <span>
          Página {page} de {totalPages}
        </span>
        <button
          type="button"
          onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
          disabled={page >= totalPages || loading}
          className="h-8 rounded-md border border-fundo-borda px-3 disabled:opacity-40"
        >
          Próxima
        </button>
      </div>
    </div>
  )
}

function StatusPill({ active, yes, no }: { active: boolean; yes: string; no: string }) {
  return (
    <span className={`rounded-full border px-2 py-1 text-[11px] ${active ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300' : 'border-amber-500/30 bg-amber-500/10 text-amber-300'}`}>
      {active ? yes : no}
    </span>
  )
}
