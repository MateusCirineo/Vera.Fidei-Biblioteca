import assert from 'node:assert/strict'
import test from 'node:test'

import {
  blocksPlayPurchaseForExternalBilling,
  GOOGLE_PLAY_PACKAGE_NAME,
  GOOGLE_PLAY_PRODUCT_IDS,
  finishablePurchaseIndexes,
  parsePlayBillingCatalog,
  parsePlayBillingStatus,
  parsePlaySyncResponse,
  playOfferTerms,
  playPurchasePreflightBillingState,
  playSyncOutcome,
  replacementModeForPlans,
  selectPlayOffer,
} from '../lib/play-billing'

test('aceita somente catalogo Play habilitado para o pacote oficial e conta ofuscada valida', () => {
  const catalog = parsePlayBillingCatalog({
    enabled: true,
    package_name: GOOGLE_PLAY_PACKAGE_NAME,
    obfuscated_account_id: 'account-hash-123',
    products: [
      {
        plan: 'catequista',
        product_id: 'vf.sub.catequista',
        base_plan_id: 'monthly',
      },
      {
        plan: 'apologeta',
        product_id: 'vf.sub.apologeta',
        base_plan_id: 'monthly',
      },
      {
        plan: 'patristico',
        product_id: 'vf.sub.patristico',
        base_plan_id: 'monthly',
      },
      {
        plan: 'magisterio',
        product_id: 'vf.sub.magisterio',
        base_plan_id: 'monthly',
      },
    ],
  })

  assert.equal(catalog.enabled, true)
  assert.equal(catalog.package_name, GOOGLE_PLAY_PACKAGE_NAME)
  assert.equal(catalog.obfuscated_account_id, 'account-hash-123')
  assert.deepEqual(catalog.products, [
    {
      plan: 'catequista',
      product_id: 'vf.sub.catequista',
      base_plan_id: 'monthly',
    },
    {
      plan: 'apologeta',
      product_id: 'vf.sub.apologeta',
      base_plan_id: 'monthly',
    },
    {
      plan: 'patristico',
      product_id: 'vf.sub.patristico',
      base_plan_id: 'monthly',
    },
    {
      plan: 'magisterio',
      product_id: 'vf.sub.magisterio',
      base_plan_id: 'monthly',
    },
  ])
})

test('catalogo Play falha fechado para pacote ou conta invalidos', () => {
  const base = {
    enabled: true,
    package_name: GOOGLE_PLAY_PACKAGE_NAME,
    obfuscated_account_id: 'account-hash-123',
    products: Object.entries(GOOGLE_PLAY_PRODUCT_IDS).map(([plan, product_id]) => ({
      plan,
      product_id,
      base_plan_id: 'monthly',
    })),
  }

  assert.equal(parsePlayBillingCatalog({ ...base, package_name: 'com.example.clone' }).enabled, false)
  assert.equal(parsePlayBillingCatalog({ ...base, obfuscated_account_id: null }).enabled, false)

  const oversized = parsePlayBillingCatalog({
    ...base,
    obfuscated_account_id: 'a'.repeat(65),
  })
  assert.equal(oversized.enabled, false)
  assert.equal(oversized.obfuscated_account_id, null)
  assert.equal(parsePlayBillingCatalog({ ...base, products: [] }).enabled, false)
  assert.deepEqual(parsePlayBillingCatalog({
    enabled: false,
    package_name: GOOGLE_PLAY_PACKAGE_NAME,
    obfuscated_account_id: null,
    products: [],
  }), {
    enabled: false,
    package_name: GOOGLE_PLAY_PACKAGE_NAME,
    obfuscated_account_id: null,
    products: [],
  })
  assert.equal(parsePlayBillingCatalog({
    ...base,
    products: base.products.map(product => (
      product.plan === 'catequista' ? { ...product, plan: 'CATEQUISTA' } : product
    )),
  }).enabled, false)
  assert.equal(parsePlayBillingCatalog({
    ...base,
    products: base.products.map(product => (
      product.plan === 'catequista'
        ? { ...product, product_id: 'vf.sub.apologeta' }
        : product.plan === 'apologeta'
          ? { ...product, product_id: 'vf.sub.catequista' }
          : product
    )),
  }).enabled, false)
  assert.equal(parsePlayBillingCatalog({
    ...base,
    products: base.products.map(product => (
      product.plan === 'magisterio' ? { ...product, base_plan_id: 'annual' } : product
    )),
  }).enabled, false)
})

test('catalogo com duplicatas, extras ou mapeamento permutado falha fechado', () => {
  const catalog = parsePlayBillingCatalog({
    enabled: true,
    package_name: GOOGLE_PLAY_PACKAGE_NAME,
    obfuscated_account_id: 'account-hash-123',
    products: [
      { plan: 'catequista', product_id: 'product-a', base_plan_id: 'monthly' },
      { plan: 'catequista', product_id: 'product-b', base_plan_id: 'annual' },
      { plan: 'apologeta', product_id: 'product-a', base_plan_id: 'monthly' },
      { plan: 'apologeta', product_id: 'product-b', base_plan_id: 'monthly' },
      { plan: 'desconhecido', product_id: 'product-c', base_plan_id: 'monthly' },
    ],
  })

  assert.equal(catalog.enabled, false)
  assert.deepEqual(catalog.products, [
    { plan: 'catequista', product_id: 'product-a', base_plan_id: 'monthly' },
    { plan: 'apologeta', product_id: 'product-b', base_plan_id: 'monthly' },
  ])
})

test('normaliza respostas de sync e restore sem confiar em tipos coerciveis', () => {
  const sync = parsePlaySyncResponse({
    synced: true,
    restored: false,
    plan: 'apologeta',
    billing_status: 'active',
    active_product_id: 'vf.sub.apologeta',
    results: [
      {
        index: 0,
        accepted: true,
        entitlement_granted: true,
        finish_transaction: true,
        state: 'purchased',
      },
      {
        index: 1,
        accepted: 'true',
        entitlement_granted: 1,
        finish_transaction: 'true',
        state: '',
        message: '  aguardando confirmacao  ',
      },
      { index: -1, accepted: true },
      { index: 1.5, accepted: true },
      { index: '2', accepted: true },
    ],
  }, 'sync')

  assert.equal(sync.completed, true)
  assert.equal(sync.plan, 'apologeta')
  assert.equal(sync.results.length, 2)
  assert.deepEqual(sync.results[0], {
    index: 0,
    accepted: true,
    entitlement_granted: true,
    finish_transaction: true,
    state: 'purchased',
    message: null,
  })
  assert.deepEqual(sync.results[1], {
    index: 1,
    accepted: false,
    entitlement_granted: false,
    finish_transaction: false,
    state: 'unknown',
    message: 'aguardando confirmacao',
  })

  assert.equal(parsePlaySyncResponse({ synced: true }, 'restore').completed, false)
  assert.equal(parsePlaySyncResponse({ restored: true }, 'restore').completed, true)
})

test('finaliza somente compras explicitamente aceitas, concedidas e liberadas pelo backend', () => {
  const response = parsePlaySyncResponse({
    synced: true,
    results: [
      { index: 0, accepted: true, entitlement_granted: true, finish_transaction: true },
      { index: 0, accepted: true, entitlement_granted: true, finish_transaction: true },
      { index: 1, accepted: false, entitlement_granted: true, finish_transaction: true },
      { index: 2, accepted: true, entitlement_granted: false, finish_transaction: true },
      { index: 3, accepted: true, entitlement_granted: true, finish_transaction: false },
      { index: 4, accepted: true, entitlement_granted: true, finish_transaction: true },
    ],
  }, 'sync')

  assert.deepEqual(finishablePurchaseIndexes(response, 4), [0])
})

test('nunca trata sync aceito ou pagamento pendente como entitlement ativo', () => {
  const pending = parsePlaySyncResponse({
    synced: true,
    results: [{
      index: 0,
      accepted: true,
      entitlement_granted: false,
      finish_transaction: false,
      state: 'pending',
    }],
  }, 'sync')
  assert.equal(playSyncOutcome(pending, 'sync').kind, 'pending')

  const expired = parsePlaySyncResponse({
    restored: true,
    results: [{
      index: 0,
      accepted: true,
      entitlement_granted: false,
      finish_transaction: false,
      state: 'expired',
    }],
  }, 'restore')
  assert.equal(playSyncOutcome(expired, 'restore').kind, 'error')

  const mixed = parsePlaySyncResponse({
    restored: false,
    results: [
      { index: 0, accepted: false, entitlement_granted: false, finish_transaction: false, state: 'expired' },
      { index: 1, accepted: true, entitlement_granted: true, finish_transaction: true, state: 'active' },
    ],
  }, 'restore')
  assert.equal(playSyncOutcome(mixed, 'restore').kind, 'success')
})

test('status de cobranca aceita apenas strings nao vazias', () => {
  assert.deepEqual(parsePlayBillingStatus({
    plan: '  catequista ',
    billing_provider: 'google_play',
    billing_status: '',
    active_product_id: 123,
    current_period_end: 'invalido',
  }), {
    plan: 'catequista',
    billing_provider: 'google_play',
    billing_status: null,
    active_product_id: null,
    current_period_end: null,
  })
})

test('seleciona apenas oferta compravel e inequivoca', () => {
  const monthly = {
    basePlanIdAndroid: 'monthly',
    displayPrice: 'R$ 9,90',
    offerTokenAndroid: 'token-monthly',
  }
  const annual = {
    basePlanIdAndroid: 'annual',
    displayPrice: 'R$ 99,90',
    offerTokenAndroid: 'token-annual',
  }
  const unavailable = {
    basePlanIdAndroid: 'legacy',
    displayPrice: 'R$ 1,00',
    offerTokenAndroid: null,
  }

  assert.equal(selectPlayOffer([monthly, annual, unavailable], 'monthly'), monthly)
  assert.equal(selectPlayOffer([monthly, annual], 'missing'), null)
  assert.equal(selectPlayOffer([monthly, annual], null), null)
  assert.equal(selectPlayOffer([unavailable], null), null)
  assert.equal(selectPlayOffer([monthly, unavailable], null), monthly)

  const introductory = {
    ...monthly,
    id: 'trial-seven-days',
    offerTokenAndroid: 'token-trial',
  }
  assert.equal(selectPlayOffer([introductory, monthly], 'monthly'), monthly)
  assert.equal(selectPlayOffer([
    introductory,
    { ...introductory, id: 'discount', offerTokenAndroid: 'token-discount' },
  ], 'monthly'), null)
})

test('exibe todos os termos localizados retornados pelo Google Play', () => {
  const terms = playOfferTerms({
    basePlanIdAndroid: 'monthly',
    displayPrice: 'R$ 9,90',
    offerTokenAndroid: 'token-monthly',
    pricingPhasesAndroid: {
      pricingPhaseList: [
        {
          billingCycleCount: 1,
          billingPeriod: 'P7D',
          formattedPrice: 'Gratis',
          priceAmountMicros: '0',
          recurrenceMode: 2,
        },
        {
          billingCycleCount: 0,
          billingPeriod: 'P1M',
          formattedPrice: 'R$ 9,90',
          priceAmountMicros: '9900000',
          recurrenceMode: 1,
        },
      ],
    },
  })

  assert.equal(terms, `Gratis a cada 7 dias por 1 ciclo \u00b7 depois, R$ 9,90 a cada 1 m\u00eas`)
  assert.equal(playOfferTerms(null), '')
  assert.equal(playOfferTerms({ displayPrice: 'R$ 12,34' }), 'R$ 12,34')
})

test('troca de plano cobra proporcionalmente no upgrade e adia downgrade', () => {
  assert.equal(replacementModeForPlans('catequista', 'apologeta'), 'charge-prorated-price')
  assert.equal(replacementModeForPlans('apologeta', 'magisterio'), 'charge-prorated-price')
  assert.equal(replacementModeForPlans('magisterio', 'patristico'), 'deferred')
  assert.equal(replacementModeForPlans('patristico', 'catequista'), 'deferred')
  assert.equal(replacementModeForPlans('apologeta', 'apologeta'), null)
})

test('bloqueia compra Play para toda assinatura Stripe ativa ou recuperavel', () => {
  const recoverable = [
    'active',
    'trialing',
    'past_due',
    'checkout_pending',
    'pending_payment',
    'incomplete',
    'paused',
    'unpaid',
    'processing',
    'requires_action',
    'payment_failed',
  ]
  for (const billing_status of recoverable) {
    assert.equal(blocksPlayPurchaseForExternalBilling({
      billing_provider: 'stripe',
      billing_status,
    }, Date.UTC(2026, 7, 25)), true, billing_status)
  }

  assert.equal(blocksPlayPurchaseForExternalBilling({
    billing_provider: 'stripe',
    billing_status: null,
  }, Date.UTC(2026, 7, 25)), true)
  assert.equal(blocksPlayPurchaseForExternalBilling({
    billing_provider: 'stripe',
    billing_status: 'future_stripe_state',
  }, Date.UTC(2026, 7, 25)), true)
})

test('canceled Stripe bloqueia enquanto vigente e libera apenas depois do periodo', () => {
  const now = Date.UTC(2026, 7, 25)
  assert.equal(blocksPlayPurchaseForExternalBilling({
    billing_provider: 'stripe',
    billing_status: 'canceled',
    billing_current_period_end: '2026-09-01T00:00:00Z',
  }, now), true)
  assert.equal(blocksPlayPurchaseForExternalBilling({
    billing_provider: 'stripe',
    billing_status: 'canceled',
    billing_current_period_end: '2026-08-01T00:00:00Z',
  }, now), false)
  assert.equal(blocksPlayPurchaseForExternalBilling({
    billing_provider: 'stripe',
    billing_status: 'cancelled',
  }, now), true)
  assert.equal(blocksPlayPurchaseForExternalBilling({
    billing_provider: 'stripe',
    billing_status: 'canceled',
    billing_current_period_end: Math.floor(Date.UTC(2026, 8, 1) / 1_000),
  }, now), true)
  assert.equal(blocksPlayPurchaseForExternalBilling({
    billing_provider: 'stripe',
    billing_status: 'canceled',
    billing_current_period_end: -1,
  }, now), true)
  assert.equal(blocksPlayPurchaseForExternalBilling({
    billing_provider: 'stripe',
    billing_status: 'canceled',
    billing_current_period_end: '2026-08-25T00:00:00',
  }, Date.UTC(2026, 7, 25, 1)), false)
})

test('nao bloqueia Google Play nem estados externos comprovadamente terminais', () => {
  for (const billing_status of [
    'checkout_expired',
    'checkout_failed',
    'ended',
    'expired',
    'inactive',
    'incomplete_expired',
    'revoked',
  ]) {
    assert.equal(blocksPlayPurchaseForExternalBilling({
      billing_provider: 'stripe',
      billing_status,
    }), false, billing_status)
  }
  assert.equal(blocksPlayPurchaseForExternalBilling({
    billing_provider: 'google_play',
    billing_status: 'active',
  }), false)
  assert.equal(blocksPlayPurchaseForExternalBilling({
    billing_provider: null,
    billing_status: 'checkout_pending',
  }), false)
  assert.equal(blocksPlayPurchaseForExternalBilling({
    billing_provider: 'stripe',
    billing_status: 'checkout_complete',
  }), true)
})

test('preflight usa somente status fresco e o periodo autoritativo do backend', () => {
  const now = Date.UTC(2026, 7, 25)
  const canceledCurrent = parsePlayBillingStatus({
    plan: 'fiel',
    billing_provider: 'stripe',
    billing_status: 'canceled',
    active_product_id: null,
    current_period_end: '2026-09-01T00:00:00Z',
  })
  assert.equal(blocksPlayPurchaseForExternalBilling(
    playPurchasePreflightBillingState(canceledCurrent),
    now,
  ), true)

  const canceledExpired = parsePlayBillingStatus({
    plan: 'fiel',
    billing_provider: 'stripe',
    billing_status: 'canceled',
    active_product_id: null,
    current_period_end: '2026-08-01T00:00:00Z',
  })
  assert.equal(blocksPlayPurchaseForExternalBilling(
    playPurchasePreflightBillingState(canceledExpired),
    now,
  ), false)

  const staleUserSnapshot = {
    billing_provider: 'stripe',
    billing_status: 'checkout_pending',
  }
  assert.equal(blocksPlayPurchaseForExternalBilling(staleUserSnapshot, now), true)
  const freshFreeAccount = parsePlayBillingStatus({
    plan: 'fiel',
    billing_provider: null,
    billing_status: null,
    active_product_id: null,
    current_period_end: null,
  })
  assert.equal(blocksPlayPurchaseForExternalBilling(
    playPurchasePreflightBillingState(freshFreeAccount),
    now,
  ), false)

  const expiredCheckout = parsePlayBillingStatus({
    plan: 'fiel',
    billing_provider: 'stripe',
    billing_status: 'checkout_pending',
    active_product_id: null,
    current_period_end: '2000-01-01T00:00:00Z',
  })
  assert.equal(expiredCheckout.billing_status, 'checkout_expired')
  assert.equal(blocksPlayPurchaseForExternalBilling(
    playPurchasePreflightBillingState(expiredCheckout),
    now,
  ), false)
})

test('owner ou admin nunca pode iniciar compra Play', () => {
  for (const billing_status of ['owner', 'admin', 'administrator']) {
    assert.equal(blocksPlayPurchaseForExternalBilling(playPurchasePreflightBillingState({
      billing_provider: null,
      billing_status,
      current_period_end: null,
    })), true, billing_status)
  }
})
