'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import {
  createAdminCoupon,
  getAdminCoupons,
  type AdminCoupon,
  type AdminCouponsResponse,
} from '@/lib/api'

type CouponTab = 'available' | 'used' | 'inactive'

const TAB_LABELS: Record<CouponTab, string> = {
  available: 'Disponiveis',
  used: 'Usados',
  inactive: 'Inativos',
}

function discountLabel(coupon: AdminCoupon): string {
  if (coupon.percent_off) return `${coupon.percent_off}%`
  if (coupon.amount_off && coupon.currency) {
    return `${coupon.currency.toUpperCase()} ${(coupon.amount_off / 100).toFixed(2)}`
  }
  return 'Desconto'
}

function durationLabel(duration?: string | null): string {
  if (duration === 'forever') return 'Recorrente'
  if (duration === 'once') return 'Primeiro pagamento'
  if (duration === 'repeating') return 'Periodo limitado'
  return 'Nao informado'
}

function createdLabel(value?: string | null): string {
  if (!value) return 'Sem data'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Sem data'
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export default function CouponList() {
  const [prefix, setPrefix] = useState('COLEGIO')
  const [appliedPrefix, setAppliedPrefix] = useState('COLEGIO')
  const [tab, setTab] = useState<CouponTab>('available')
  const [data, setData] = useState<AdminCouponsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')
  const [newCode, setNewCode] = useState('')
  const [percentOff, setPercentOff] = useState('20')
  const [duration, setDuration] = useState<'once' | 'forever'>('once')
  const [maxRedemptions, setMaxRedemptions] = useState('1')
  const [creating, setCreating] = useState(false)
  const [createdMessage, setCreatedMessage] = useState('')

  const load = useCallback(async (nextPrefix = appliedPrefix) => {
    setLoading(true)
    setError('')
    try {
      const result = await getAdminCoupons(nextPrefix)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar cupons.')
    } finally {
      setLoading(false)
    }
  }, [appliedPrefix])

  useEffect(() => {
    let active = true
    getAdminCoupons('COLEGIO')
      .then((result) => {
        if (active) setData(result)
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : 'Erro ao carregar cupons.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const activeRows = useMemo(() => {
    if (!data) return []
    return data[tab]
  }, [data, tab])

  function applyFilter() {
    const clean = prefix.trim().toUpperCase()
    setAppliedPrefix(clean)
    load(clean)
  }

  async function copyCode(code: string) {
    await navigator.clipboard.writeText(code)
    setCopied(code)
    setTimeout(() => setCopied(''), 1800)
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setCreating(true)
    setError('')
    setCreatedMessage('')
    try {
      const coupon = await createAdminCoupon({
        code: newCode.trim().toUpperCase(),
        percent_off: Number(percentOff),
        duration,
        max_redemptions: maxRedemptions ? Number(maxRedemptions) : null,
      })
      setCreatedMessage(`Cupom ${coupon.code} criado com sucesso.`)
      setNewCode('')
      setPrefix('')
      setAppliedPrefix('')
      setTab('available')
      await load('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar cupom.')
    } finally {
      setCreating(false)
    }
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.22em] text-dourado/70">
            Stripe
          </p>
          <h2 className="mt-1 font-eb-garamond text-2xl text-texto">
            Cupons ativos
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-texto-terciario">
            Acompanhe os cupons do Colégio Patrístico. Cupons usados saem da lista de disponíveis automaticamente.
          </p>
        </div>
        <button
          onClick={() => load(appliedPrefix)}
          disabled={loading}
          className="self-start rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-secundario transition-colors hover:border-dourado/60 hover:text-dourado disabled:cursor-not-allowed disabled:opacity-50 lg:self-auto"
        >
          {loading ? 'Atualizando...' : 'Atualizar'}
        </button>
      </div>

      <form onSubmit={handleCreate} className="rounded-lg border border-dourado/30 bg-fundo-card p-4">
        <div className="mb-4">
          <h3 className="font-eb-garamond text-xl text-texto">Criar cupom</h3>
          <p className="mt-1 text-xs text-texto-terciario">
            O código será criado diretamente na Stripe e ficará disponível no checkout.
          </p>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <label className="block">
            <span className="mb-2 block text-xs uppercase tracking-[0.16em] text-texto-terciario">Código</span>
            <input
              required
              minLength={3}
              maxLength={50}
              pattern="[A-Za-z0-9-]+"
              value={newCode}
              onChange={(event) => setNewCode(event.target.value.toUpperCase())}
              placeholder="COLEGIO20"
              className="h-11 w-full rounded-md border border-fundo-borda bg-fundo px-3 text-sm uppercase text-texto outline-none focus:border-dourado/70"
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-xs uppercase tracking-[0.16em] text-texto-terciario">Desconto (%)</span>
            <input
              required
              type="number"
              min="0.01"
              max="100"
              step="0.01"
              value={percentOff}
              onChange={(event) => setPercentOff(event.target.value)}
              className="h-11 w-full rounded-md border border-fundo-borda bg-fundo px-3 text-sm text-texto outline-none focus:border-dourado/70"
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-xs uppercase tracking-[0.16em] text-texto-terciario">Validade</span>
            <select
              value={duration}
              onChange={(event) => setDuration(event.target.value as 'once' | 'forever')}
              className="h-11 w-full rounded-md border border-fundo-borda bg-fundo px-3 text-sm text-texto outline-none focus:border-dourado/70"
            >
              <option value="once">Primeiro pagamento</option>
              <option value="forever">Todos os pagamentos</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-2 block text-xs uppercase tracking-[0.16em] text-texto-terciario">Limite de usos</span>
            <input
              type="number"
              min="1"
              max="100000"
              value={maxRedemptions}
              onChange={(event) => setMaxRedemptions(event.target.value)}
              placeholder="Sem limite"
              className="h-11 w-full rounded-md border border-fundo-borda bg-fundo px-3 text-sm text-texto outline-none focus:border-dourado/70"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={creating}
          className="mt-4 h-11 rounded-md bg-dourado px-5 text-sm font-semibold text-fundo transition-colors hover:bg-dourado/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {creating ? 'Criando...' : 'Criar cupom'}
        </button>
        {createdMessage && (
          <p className="mt-3 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">
            {createdMessage}
          </p>
        )}
      </form>

      <div className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <label className="block">
            <span className="mb-2 block text-xs uppercase tracking-[0.16em] text-texto-terciario">
              Prefixo
            </span>
            <input
              value={prefix}
              onChange={(event) => setPrefix(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') applyFilter()
              }}
              placeholder="COLEGIO"
              className="h-11 w-full rounded-md border border-fundo-borda bg-fundo px-3 text-sm uppercase text-texto outline-none transition-colors placeholder:text-texto-terciario focus:border-dourado/70"
            />
          </label>
          <button
            type="button"
            onClick={applyFilter}
            className="h-11 rounded-md bg-dourado px-4 text-sm font-semibold text-fundo transition-colors hover:bg-dourado/90"
          >
            Filtrar cupons
          </button>
        </div>
        {data && (
          <p className="mt-3 text-xs text-texto-terciario">
            Modo {data.mode === 'producao' ? 'produção' : 'teste'} · Prefixo {data.prefix || 'todos'} · {data.total} cupons encontrados.
          </p>
        )}
      </div>

      {error && (
        <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-3">
        <SummaryTile label="Disponiveis" value={data?.available_count ?? 0} active={tab === 'available'} onClick={() => setTab('available')} />
        <SummaryTile label="Usados" value={data?.used_count ?? 0} active={tab === 'used'} onClick={() => setTab('used')} />
        <SummaryTile label="Inativos" value={data?.inactive_count ?? 0} active={tab === 'inactive'} onClick={() => setTab('inactive')} />
      </div>

      <div className="overflow-hidden rounded-lg border border-fundo-borda bg-fundo-card">
        <div className="border-b border-fundo-borda bg-fundo/60 px-4 py-3">
          <h3 className="font-eb-garamond text-lg text-texto">
            {TAB_LABELS[tab]}
          </h3>
          <p className="text-xs text-texto-terciario">
            {tab === 'available'
              ? 'Estes códigos ainda podem ser enviados para alunos.'
              : tab === 'used'
                ? 'Estes códigos já foram resgatados e não devem ser enviados novamente.'
                : 'Estes códigos estão desativados na Stripe.'}
          </p>
        </div>

        {loading ? (
          <p className="px-4 py-8 text-center text-sm text-texto-terciario">Carregando cupons...</p>
        ) : activeRows.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-texto-terciario">Nenhum cupom nesta lista.</p>
        ) : (
          <div className="divide-y divide-fundo-borda">
            {activeRows.map((coupon) => (
              <div key={coupon.id} className="grid gap-3 px-4 py-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <code className="break-all rounded-md border border-fundo-borda bg-fundo px-2 py-1 text-xs text-dourado">
                      {coupon.code}
                    </code>
                    <span className="rounded-full border border-fundo-borda px-2 py-0.5 text-[11px] text-texto-secundario">
                      {coupon.status_label}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-texto-terciario">
                    {discountLabel(coupon)} · {durationLabel(coupon.duration)} · Uso {coupon.times_redeemed}/{coupon.max_redemptions ?? 'sem limite'} · Criado em {createdLabel(coupon.created_at)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => copyCode(coupon.code)}
                  disabled={tab !== 'available'}
                  className="h-9 rounded-md border border-dourado/40 px-3 text-xs font-semibold text-dourado transition-colors hover:bg-dourado hover:text-fundo disabled:cursor-not-allowed disabled:border-fundo-borda disabled:text-texto-terciario disabled:hover:bg-transparent"
                >
                  {copied === coupon.code ? 'Copiado' : 'Copiar'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

function SummaryTile({
  label,
  value,
  active,
  onClick,
}: {
  label: string
  value: number
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'rounded-lg border p-4 text-left transition-colors',
        active
          ? 'border-dourado bg-dourado/10'
          : 'border-fundo-borda bg-fundo-card hover:border-dourado/60',
      ].join(' ')}
    >
      <p className="text-xs uppercase tracking-[0.18em] text-texto-terciario">{label}</p>
      <p className="mt-2 font-eb-garamond text-2xl text-dourado">{value.toLocaleString('pt-BR')}</p>
    </button>
  )
}
