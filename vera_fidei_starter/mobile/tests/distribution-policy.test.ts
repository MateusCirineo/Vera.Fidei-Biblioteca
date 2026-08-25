import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  allowsAccountWeb,
  allowsExternalBilling,
  allowsPlayBilling,
  isPdfNavigationAllowed,
  isReaderPdfNavigationAllowed,
  normalizeDistributionMode,
  plansRouteForMode,
  subscriptionGatePolicy,
} from '../lib/distribution-policy'

test('o modo de distribuição falha fechado como reader', () => {
  assert.equal(normalizeDistributionMode(undefined), 'reader')
  assert.equal(normalizeDistributionMode('reader'), 'reader')
  assert.equal(normalizeDistributionMode('production'), 'reader')
  assert.equal(normalizeDistributionMode('DIRECT'), 'reader')
  assert.equal(normalizeDistributionMode('direct'), 'direct')
  assert.equal(normalizeDistributionMode('play'), 'play')
  assert.equal(normalizeDistributionMode('PLAY'), 'reader')
})

test('reader não expõe conta web, planos ou cobrança externa', () => {
  assert.equal(allowsAccountWeb('reader', 'profile'), false)
  assert.equal(allowsAccountWeb('reader', 'plans'), false)
  assert.equal(allowsExternalBilling('reader'), false)
  assert.equal(allowsAccountWeb('direct', 'profile'), true)
  assert.equal(allowsAccountWeb('direct', 'plans'), true)
  assert.equal(allowsExternalBilling('direct'), true)
})

test('play permite cobranca somente no Android e nunca abre cobranca ou conta web', () => {
  assert.equal(allowsPlayBilling('play', 'android'), true)
  assert.equal(allowsPlayBilling('play', 'ios'), false)
  assert.equal(allowsPlayBilling('play', 'web'), false)
  assert.equal(allowsPlayBilling('reader', 'android'), false)
  assert.equal(allowsPlayBilling('direct', 'android'), false)
  assert.equal(allowsExternalBilling('play'), false)
  assert.equal(allowsAccountWeb('play', 'profile'), false)
  assert.equal(allowsAccountWeb('play', 'plans'), false)
})

test('cada modo encaminha planos apenas para a superficie de cobranca permitida', () => {
  assert.equal(plansRouteForMode('reader', 'android'), null)
  assert.equal(plansRouteForMode('direct', 'android'), 'ContaWeb')
  assert.equal(plansRouteForMode('direct', 'ios'), 'ContaWeb')
  assert.equal(plansRouteForMode('play', 'android'), 'PlayPlans')
  assert.equal(plansRouteForMode('play', 'ios'), null)
  assert.equal(plansRouteForMode('play', 'web'), null)
  assert.equal(plansRouteForMode('play', undefined), null)

  for (const resource of ['pdf', 'verification', 'search'] as const) {
    const policy = subscriptionGatePolicy('play', resource)
    assert.equal(policy.showPlansAction, true)
    assert.match(policy.message, /Google Play/i)
    assert.doesNotMatch(policy.message, /stripe|checkout|https?:/i)
  }
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

test('play usa a mesma allowlist restrita do leitor e direct mantém o mesmo origin', () => {
  const base = 'https://verafidei.oialfred.com'
  for (const allowed of [
    'about:blank',
    `${base}/api/auth/mobile-web-session`,
    `${base}/visualizar/28?page=12`,
    `${base}/viewer/pdf?file=%2Fapi%2Fpdfs%2F28&page=12`,
    `${base}/api/pdfs/28`,
  ]) {
    assert.equal(isPdfNavigationAllowed('play', allowed, base), true, allowed)
  }
  for (const blocked of [
    `${base}/perfil`,
    `${base}/planos`,
    `${base}/api/billing/checkout`,
    'https://checkout.stripe.com/c/pay/test',
  ]) {
    assert.equal(isPdfNavigationAllowed('play', blocked, base), false, blocked)
  }

  assert.equal(isPdfNavigationAllowed('direct', `${base}/perfil`, base), true)
  assert.equal(isPdfNavigationAllowed('direct', `${base}/planos`, base), true)
  assert.equal(isPdfNavigationAllowed('direct', 'https://example.com/perfil', base), false)
})

test('perfis EAS separam preview direct de produção reader', () => {
  const config = JSON.parse(readFileSync(new URL('../eas.json', import.meta.url), 'utf8'))
  assert.equal(config.build.preview.env.EXPO_PUBLIC_DISTRIBUTION_MODE, 'direct')
  assert.equal(config.build.preview.autoIncrement, true)
  assert.equal(config.build.production.env.EXPO_PUBLIC_DISTRIBUTION_MODE, 'reader')
  assert.equal(config.build.production.autoIncrement, true)
  assert.equal(config.build['production-play'].env.EXPO_PUBLIC_DISTRIBUTION_MODE, 'play')
  assert.equal(config.build['production-play'].env.APP_VARIANT, 'production')
  assert.equal(config.build['production-play'].distribution, 'store')
  assert.equal(config.build['production-play'].android.buildType, 'app-bundle')
  assert.equal(config.build['production-play'].autoIncrement, true)
})
