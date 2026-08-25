export const GOOGLE_PLAY_PACKAGE_NAME = 'com.verafidei.app'

export const PAID_PLAN_KEYS = ['catequista', 'apologeta', 'patristico', 'magisterio'] as const

export type PaidPlanKey = (typeof PAID_PLAN_KEYS)[number]

export const GOOGLE_PLAY_BASE_PLAN_ID = 'monthly'

export const GOOGLE_PLAY_PRODUCT_IDS = {
  catequista: 'vf.sub.catequista',
  apologeta: 'vf.sub.apologeta',
  patristico: 'vf.sub.patristico',
  magisterio: 'vf.sub.magisterio',
} as const satisfies Record<PaidPlanKey, string>

export type PlayPlanDetails = {
  label: string
  audience: string
  verificationLimit: string
  features: string[]
}

export const PLAY_PLAN_DETAILS: Record<PaidPlanKey, PlayPlanDetails> = {
  catequista: {
    label: 'Catequista',
    audience: 'Aulas e grupos',
    verificationLimit: '25 verificações por mês',
    features: ['Laudos em PDF', 'Referência exata da fonte', 'Histórico completo da conta'],
  },
  apologeta: {
    label: 'Apologeta',
    audience: 'Pesquisa e defesa da fé',
    verificationLimit: '50 verificações por mês',
    features: ['Tudo do Catequista', 'Acesso aos PDFs', 'Contexto patrístico mais completo'],
  },
  patristico: {
    label: 'Patrístico',
    audience: 'Instituições pequenas',
    verificationLimit: '100 verificações por mês',
    features: ['Tudo do Apologeta', 'Painel institucional', 'Gestão de membros e relatório mensal'],
  },
  magisterio: {
    label: 'Magistério',
    audience: 'Equipes e integrações',
    verificationLimit: 'Verificações ilimitadas',
    features: ['Tudo do Patrístico', 'API dedicada', 'Chaves e integração com sistemas externos'],
  },
}

export type PlayCatalogProduct = {
  plan: PaidPlanKey
  product_id: string
  base_plan_id: string | null
}

export type PlayBillingCatalog = {
  enabled: boolean
  package_name: string
  obfuscated_account_id: string | null
  products: PlayCatalogProduct[]
}

export type PlayPurchaseInput = {
  purchase_token: string
  product_id?: string
}

export type PlaySyncResult = {
  index: number
  accepted: boolean
  entitlement_granted: boolean
  finish_transaction: boolean
  state: string
  message: string | null
}

export type PlaySyncResponse = {
  completed: boolean
  plan: string | null
  billing_status: string | null
  active_product_id: string | null
  results: PlaySyncResult[]
}

export type PlayBillingStatus = {
  plan: string | null
  billing_provider: string | null
  billing_status: string | null
  active_product_id: string | null
  current_period_end: string | null
}

export type BillingStateLike = {
  billing_provider?: unknown
  billing_status?: unknown
  billing_current_period_end?: unknown
}

/** Builds the purchase preflight exclusively from the fresh backend status. */
export function playPurchasePreflightBillingState(
  freshStatus: Pick<PlayBillingStatus, 'billing_provider' | 'billing_status' | 'current_period_end'> | null | undefined,
): BillingStateLike {
  return {
    billing_provider: cleanString(freshStatus?.billing_provider),
    billing_status: cleanString(freshStatus?.billing_status),
    billing_current_period_end: freshStatus?.current_period_end ?? null,
  }
}

const GOOGLE_BILLING_PROVIDERS = new Set(['google_play', 'google-play', 'play'])
const TERMINAL_EXTERNAL_BILLING_STATUSES = new Set([
  'checkout_expired',
  'checkout_failed',
  'ended',
  'expired',
  'inactive',
  'incomplete_expired',
  'revoked',
])
const CANCELED_BILLING_STATUSES = new Set(['canceled', 'cancelled'])
const NON_PURCHASABLE_ACCOUNT_STATUSES = new Set(['owner', 'admin', 'administrator'])

function periodEndMilliseconds(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    if (value <= 0) return null
    return value < 1_000_000_000_000 ? value * 1_000 : value
  }
  if (typeof value !== 'string' || !value.trim()) return null
  const trimmed = value.trim()
  if (/^[+-]?\d+(?:\.\d+)?$/.test(trimmed)) {
    const numeric = Number(trimmed)
    if (!Number.isFinite(numeric) || numeric <= 0) return null
    return numeric < 1_000_000_000_000 ? numeric * 1_000 : numeric
  }
  const looksLikeNaiveIsoDateTime = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(trimmed)
  const parsed = Date.parse(looksLikeNaiveIsoDateTime ? `${trimmed}Z` : trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

/** Prevents parallel billing while an external subscription can still be recovered or used. */
export function blocksPlayPurchaseForExternalBilling(
  state: BillingStateLike | null | undefined,
  nowMs = Date.now(),
): boolean {
  const status = cleanString(state?.billing_status)?.toLowerCase()
  if (status && NON_PURCHASABLE_ACCOUNT_STATUSES.has(status)) return true

  const provider = cleanString(state?.billing_provider)?.toLowerCase()
  if (!provider || GOOGLE_BILLING_PROVIDERS.has(provider)) return false

  if (!status) return true
  if (TERMINAL_EXTERNAL_BILLING_STATUSES.has(status)) return false
  if (CANCELED_BILLING_STATUSES.has(status)) {
    const periodEnd = periodEndMilliseconds(state?.billing_current_period_end)
    return periodEnd === null || periodEnd > nowMs
  }
  return true
}

type UnknownRecord = Record<string, unknown>

function asRecord(value: unknown): UnknownRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as UnknownRecord
    : null
}

function cleanString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

export function isPaidPlanKey(value: unknown): value is PaidPlanKey {
  return typeof value === 'string' && (PAID_PLAN_KEYS as readonly string[]).includes(value)
}

export function parsePlayBillingCatalog(value: unknown): PlayBillingCatalog {
  const root = asRecord(value)
  const packageName = cleanString(root?.package_name)
  const accountId = cleanString(root?.obfuscated_account_id)
  const rawProducts = Array.isArray(root?.products) ? root.products : []
  const products: PlayCatalogProduct[] = []
  const productIds = new Set<string>()
  const plans = new Set<PaidPlanKey>()

  for (const candidate of rawProducts) {
    const row = asRecord(candidate)
    const plan = cleanString(row?.plan)?.toLowerCase()
    const productId = cleanString(row?.product_id)
    if (!isPaidPlanKey(plan) || !productId || productIds.has(productId) || plans.has(plan)) continue
    products.push({
      plan,
      product_id: productId,
      base_plan_id: cleanString(row?.base_plan_id),
    })
    productIds.add(productId)
    plans.add(plan)
  }

  const exactRawMapping = rawProducts.every(candidate => {
    const row = asRecord(candidate)
    const plan = row?.plan
    return isPaidPlanKey(plan)
      && row?.product_id === GOOGLE_PLAY_PRODUCT_IDS[plan]
      && row?.base_plan_id === GOOGLE_PLAY_BASE_PLAN_ID
  })

  const enabled = root?.enabled === true
    && packageName === GOOGLE_PLAY_PACKAGE_NAME
    && Boolean(accountId && accountId.length <= 64)
    && rawProducts.length === PAID_PLAN_KEYS.length
    && products.length === PAID_PLAN_KEYS.length
    && exactRawMapping
    && products.every(product => (
      product.product_id === GOOGLE_PLAY_PRODUCT_IDS[product.plan]
      && product.base_plan_id === GOOGLE_PLAY_BASE_PLAN_ID
    ))

  return {
    enabled,
    package_name: packageName ?? '',
    obfuscated_account_id: accountId && accountId.length <= 64 ? accountId : null,
    products,
  }
}

export function parsePlaySyncResponse(value: unknown, operation: 'sync' | 'restore'): PlaySyncResponse {
  const root = asRecord(value)
  const rawResults = Array.isArray(root?.results) ? root.results : []
  const results: PlaySyncResult[] = []

  for (const candidate of rawResults) {
    const row = asRecord(candidate)
    if (!row) continue
    const index = row?.index
    if (typeof index !== 'number' || !Number.isSafeInteger(index) || index < 0) continue
    results.push({
      index,
      accepted: row.accepted === true,
      entitlement_granted: row.entitlement_granted === true,
      finish_transaction: row.finish_transaction === true,
      state: cleanString(row.state) ?? 'unknown',
      message: cleanString(row.message),
    })
  }

  return {
    completed: operation === 'restore' ? root?.restored === true : root?.synced === true,
    plan: cleanString(root?.plan),
    billing_status: cleanString(root?.billing_status),
    active_product_id: cleanString(root?.active_product_id),
    results,
  }
}

export function parsePlayBillingStatus(value: unknown): PlayBillingStatus {
  const root = asRecord(value)
  const rawCurrentPeriodEnd = cleanString(root?.current_period_end)
  const currentPeriodEnd = periodEndMilliseconds(rawCurrentPeriodEnd) === null
    ? null
    : rawCurrentPeriodEnd
  const rawBillingStatus = cleanString(root?.billing_status)
  const billingStatus = rawBillingStatus?.toLowerCase() === 'checkout_pending'
    && currentPeriodEnd !== null
    && periodEndMilliseconds(currentPeriodEnd)! <= Date.now()
    ? 'checkout_expired'
    : rawBillingStatus
  return {
    plan: cleanString(root?.plan),
    billing_provider: cleanString(root?.billing_provider),
    billing_status: billingStatus,
    active_product_id: cleanString(root?.active_product_id),
    current_period_end: currentPeriodEnd,
  }
}

export function finishablePurchaseIndexes(response: PlaySyncResponse, purchaseCount: number): number[] {
  return [...new Set(response.results
    .filter(result => (
      result.index < purchaseCount
      && result.accepted
      && result.entitlement_granted
      && result.finish_transaction
    ))
    .map(result => result.index))]
}

export type PlaySyncOutcome = {
  kind: 'success' | 'pending' | 'error'
  message: string
}

export function playSyncOutcome(
  response: PlaySyncResponse,
  operation: 'sync' | 'restore',
): PlaySyncOutcome {
  const granted = response.results.find(result => result.entitlement_granted)
  if (granted) {
    return {
      kind: 'success',
      message: granted.message || (operation === 'restore'
        ? 'Assinatura restaurada e conta atualizada.'
        : 'Assinatura confirmada e conta atualizada.'),
    }
  }

  const pending = response.results.find(result => (
    !result.entitlement_granted && result.state.toLowerCase().includes('pending')
  ))
  if (pending) {
    return {
      kind: 'pending',
      message: pending.message || 'Pagamento pendente. O acesso será liberado somente após a confirmação do Google Play.',
    }
  }

  const rejected = response.results.find(result => !result.accepted || !result.entitlement_granted)
  return {
    kind: 'error',
    message: rejected?.message || (response.completed
      ? 'A sincronização terminou, mas nenhuma assinatura ativa foi confirmada.'
      : 'O servidor não confirmou a sincronização da assinatura.'),
  }
}

export type PlayOfferLike = {
  basePlanIdAndroid?: string | null
  displayPrice: string
  id?: string | null
  offerTokenAndroid?: string | null
  pricingPhasesAndroid?: {
    pricingPhaseList: {
      billingCycleCount: number
      billingPeriod: string
      formattedPrice: string
      priceAmountMicros: string
      recurrenceMode: number
    }[]
  } | null
}

export function selectPlayOffer<T extends PlayOfferLike>(
  offers: readonly T[],
  basePlanId: string | null,
): T | null {
  const purchasable = offers.filter(offer => cleanString(offer.offerTokenAndroid))
  if (basePlanId) {
    const matching = purchasable.filter(offer => offer.basePlanIdAndroid === basePlanId)
    if (matching.length === 1) return matching[0]
    const regularBasePlan = matching.filter(offer => !cleanString(offer.id))
    return regularBasePlan.length === 1 ? regularBasePlan[0] : null
  }
  return purchasable.length === 1 ? purchasable[0] : null
}

function billingPeriodLabel(period: string): string {
  const match = /^P(\d+)([DWMY])$/.exec(period)
  if (!match) return period
  const amount = Number(match[1])
  const singular: Record<string, string> = { D: 'dia', W: 'semana', M: 'mês', Y: 'ano' }
  const plural: Record<string, string> = { D: 'dias', W: 'semanas', M: 'meses', Y: 'anos' }
  return `${amount} ${amount === 1 ? singular[match[2]] : plural[match[2]]}`
}

export function playOfferTerms(offer: PlayOfferLike | null): string {
  const phases = offer?.pricingPhasesAndroid?.pricingPhaseList ?? []
  if (phases.length === 0) return offer?.displayPrice ?? ''
  return phases.map((phase, index) => {
    const duration = billingPeriodLabel(phase.billingPeriod)
    const cycles = phase.billingCycleCount > 0 ? ` por ${phase.billingCycleCount} ciclo${phase.billingCycleCount === 1 ? '' : 's'}` : ''
    const prefix = index === 0 ? '' : 'depois, '
    return `${prefix}${phase.formattedPrice} a cada ${duration}${cycles}`
  }).join(' · ')
}

export function replacementModeForPlans(
  currentPlan: PaidPlanKey,
  targetPlan: PaidPlanKey,
): 'charge-prorated-price' | 'deferred' | null {
  const current = PAID_PLAN_KEYS.indexOf(currentPlan)
  const target = PAID_PLAN_KEYS.indexOf(targetPlan)
  if (current === target) return null
  return target > current ? 'charge-prorated-price' : 'deferred'
}
