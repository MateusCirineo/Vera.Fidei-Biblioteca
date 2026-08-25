import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  allowsAccountWeb,
  allowsExternalBilling,
  isReaderPdfNavigationAllowed,
  normalizeDistributionMode,
  subscriptionGatePolicy,
} from '../lib/distribution-policy'

test('o modo de distribuição falha fechado como reader', () => {
  assert.equal(normalizeDistributionMode(undefined), 'reader')
  assert.equal(normalizeDistributionMode('reader'), 'reader')
  assert.equal(normalizeDistributionMode('production'), 'reader')
  assert.equal(normalizeDistributionMode('DIRECT'), 'reader')
  assert.equal(normalizeDistributionMode('direct'), 'direct')
})

test('reader não expõe conta web, planos ou cobrança externa', () => {
  assert.equal(allowsAccountWeb('reader', 'profile'), false)
  assert.equal(allowsAccountWeb('reader', 'plans'), false)
  assert.equal(allowsExternalBilling('reader'), false)
  assert.equal(allowsAccountWeb('direct', 'profile'), true)
  assert.equal(allowsAccountWeb('direct', 'plans'), true)
  assert.equal(allowsExternalBilling('direct'), true)
})

test('avisos do reader informam assinatura sem CTA ou link', () => {
  for (const resource of ['pdf', 'verification', 'search'] as const) {
    const policy = subscriptionGatePolicy('reader', resource)
    assert.equal(policy.showPlansAction, false)
    assert.match(policy.message, /assinatura ativa/i)
    assert.doesNotMatch(policy.message, /ver planos|compr|checkout|stripe|https?:/i)
  }
  assert.equal(subscriptionGatePolicy('direct', 'pdf').showPlansAction, true)
})

test('reader limita a WebView aos caminhos indispensáveis do PDF', () => {
  const base = 'https://verafidei.oialfred.com'
  assert.equal(isReaderPdfNavigationAllowed('about:blank', base), true)
  assert.equal(isReaderPdfNavigationAllowed(`${base}/api/auth/mobile-web-session`, base), true)
  assert.equal(isReaderPdfNavigationAllowed(`${base}/visualizar/28?page=12`, base), true)
  assert.equal(
    isReaderPdfNavigationAllowed(`${base}/viewer/pdf?file=%2Fapi%2Fpdfs%2F28&page=12`, base),
    true,
  )
  assert.equal(isReaderPdfNavigationAllowed(`${base}/api/pdfs/28`, base), true)
  assert.equal(isReaderPdfNavigationAllowed(`${base}/perfil`, base), false)
  assert.equal(isReaderPdfNavigationAllowed(`${base}/planos`, base), false)
  assert.equal(isReaderPdfNavigationAllowed(`${base}/api/billing/checkout`, base), false)
  assert.equal(isReaderPdfNavigationAllowed('https://checkout.stripe.com/c/pay/test', base), false)
})

test('perfis EAS separam preview direct de produção reader', () => {
  const config = JSON.parse(readFileSync(new URL('../eas.json', import.meta.url), 'utf8'))
  assert.equal(config.build.preview.env.EXPO_PUBLIC_DISTRIBUTION_MODE, 'direct')
  assert.equal(config.build.preview.autoIncrement, true)
  assert.equal(config.build.production.env.EXPO_PUBLIC_DISTRIBUTION_MODE, 'reader')
  assert.equal(config.build.production.autoIncrement, true)
})
