import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildMobileAccountRedirect,
  buildMobileAccountSessionUrl,
  buildMobileWebRedirect,
  buildMobileWebSessionUrl,
  isTrustedStripeNavigation,
  isTrustedWebNavigation,
  normalizeBaseUrl,
} from '../lib/url'

test('normaliza o domínio e monta o handoff seguro do visualizador', () => {
  assert.equal(normalizeBaseUrl('https://verafidei.oialfred.com///'), 'https://verafidei.oialfred.com')
  assert.equal(
    buildMobileWebSessionUrl('https://verafidei.oialfred.com/api/'),
    'https://verafidei.oialfred.com/api/auth/mobile-web-session',
  )
  assert.equal(buildMobileWebRedirect(42, 12), '/visualizar/42?page=12')
})

test('o redirect nunca inclui credencial', () => {
  const redirect = buildMobileWebRedirect(7, 1)
  assert.doesNotMatch(redirect, /token|api[_-]?key|authorization|bearer/i)
  assert.throws(() => buildMobileWebRedirect(0), /inválido/i)
})

test('a WebView permite somente HTTPS no origin oficial', () => {
  const webBase = 'https://verafidei.oialfred.com'
  assert.equal(isTrustedWebNavigation('about:blank', webBase), true)
  assert.equal(isTrustedWebNavigation('https://verafidei.oialfred.com/viewer/pdf?page=2', webBase), true)
  assert.equal(isTrustedWebNavigation('https://verafidei.oialfred.com.evil.example/', webBase), false)
  assert.equal(isTrustedWebNavigation('http://verafidei.oialfred.com/viewer/pdf', webBase), false)
  assert.equal(isTrustedWebNavigation('javascript:alert(1)', webBase), false)
})

test('o handoff da conta aceita apenas perfil e planos', () => {
  assert.equal(buildMobileAccountRedirect('profile'), '/perfil')
  assert.equal(buildMobileAccountRedirect('plans'), '/planos')
  assert.throws(() => buildMobileAccountRedirect('admin'), /inválido/i)
  assert.equal(
    buildMobileAccountSessionUrl('https://verafidei.oialfred.com/api/'),
    'https://verafidei.oialfred.com/api/auth/mobile-account-session',
  )
})

test('somente as páginas oficiais de checkout Stripe podem sair da WebView', () => {
  assert.equal(isTrustedStripeNavigation('https://checkout.stripe.com/c/pay/cs_test_123'), true)
  assert.equal(isTrustedStripeNavigation('https://billing.stripe.com/p/session/test_123'), true)
  assert.equal(isTrustedStripeNavigation('https://checkout.stripe.com.evil.example/'), false)
  assert.equal(isTrustedStripeNavigation('http://checkout.stripe.com/'), false)
  assert.equal(isTrustedStripeNavigation('https://user@checkout.stripe.com/'), false)
  assert.equal(isTrustedStripeNavigation('https://checkout.stripe.com:444/'), false)
})
