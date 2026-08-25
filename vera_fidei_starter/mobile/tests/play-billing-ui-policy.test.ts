import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

function source(path: string): string {
  return readFileSync(new URL(path, import.meta.url), 'utf8')
}

test('perfil e gates usam a rota nativa do Play sem expor checkout no modo play', () => {
  const profile = source('../screens/ProfileScreen.tsx')
  assert.match(profile, /allowsPlayBilling\(DISTRIBUTION_MODE, Platform\.OS\)/)
  assert.match(profile, /navigation\.navigate\('PlayPlans'\)/)

  for (const file of ['BookDetailScreen.tsx', 'SearchScreen.tsx', 'VerificadorScreen.tsx']) {
    const screen = source(`../screens/${file}`)
    assert.match(screen, /plansRouteForMode\(DISTRIBUTION_MODE, Platform\.OS\)/, file)
    assert.match(screen, /navigation\.navigate\('PlayPlans'\)/, file)
  }
})

test('tela Play apresenta preço localizado, restore, gestão e disclosure de renovação', () => {
  const screen = source('../screens/PlayPlansScreen.native.tsx')
  assert.match(screen, /\{plan\.displayPrice\}/)
  assert.match(screen, /\{plan\.offerTerms\}/)
  assert.match(screen, /Restaurar compras/)
  assert.match(screen, /Gerenciar no Google Play/)
  assert.match(screen, /renovada automaticamente/)
  assert.match(screen, /cancelar ou gerenciar a assinatura/)
  assert.doesNotMatch(screen, /Stripe|checkout\.stripe|https?:\/\//i)
})

test('provider finaliza a compra local somente pelos índices autorizados pelo backend', () => {
  const provider = source('../billing/PlayBillingProvider.native.tsx')
  assert.match(provider, /finishablePurchaseIndexes\(response, localPurchases\.length\)/)
  assert.match(provider, /finishTransaction\(\{ purchase: localPurchases\[index\], isConsumable: false \}\)/)
  assert.doesNotMatch(provider, /finishTransaction\([^\n]*purchase\)[^\n]*onPurchaseSuccess/)
})

test('provider repete preflight autoritativo antes da compra e usa seus dados na troca de plano', () => {
  const provider = source('../billing/PlayBillingProvider.native.tsx')
  const purchasePlan = provider.slice(
    provider.indexOf('const purchasePlan ='),
    provider.indexOf('const restore ='),
  )
  const preflightIndex = purchasePlan.indexOf('await getGooglePlayBillingStatus()')
  const requestPurchaseIndex = purchasePlan.indexOf('await requestPurchase(')
  assert.ok(preflightIndex >= 0)
  assert.ok(requestPurchaseIndex > preflightIndex)
  assert.match(purchasePlan, /const freshActiveProductId = freshStatus\.active_product_id/)
  assert.match(purchasePlan, /oldProductId: freshActiveProductId/)
  assert.match(purchasePlan, /playPurchasePreflightBillingState\(freshStatus\)/)
  assert.match(purchasePlan, /blocksPlayPurchaseForExternalBilling\(preflightBillingState\)/)
  assert.doesNotMatch(purchasePlan, /blocksPlayPurchaseForExternalBilling\(user\)/)
  assert.doesNotMatch(purchasePlan, /user\?\.billing_(?:provider|status|current_period_end)/)
  assert.match(provider, /!billingStateVerified \|\| !connected/)
})

test('WebView aplica a allowlist PDF ao modo play e não a navegação ampla do direct', () => {
  const screen = source('../screens/PdfWebViewScreen.native.tsx')
  assert.match(screen, /isPdfNavigationAllowed\(DISTRIBUTION_MODE, request\.url, WEB_BASE\)/)
  assert.doesNotMatch(screen, /DISTRIBUTION_MODE === 'reader'[^\n]*isAccount/)
})
