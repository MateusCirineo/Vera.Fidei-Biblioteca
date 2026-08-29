import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const serviceWorker = readFileSync(
  new URL('../public/sw.js', import.meta.url),
  'utf8',
)
const homePage = readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8')

test('navigation redirects stay intact instead of becoming the offline page', () => {
  const redirectGuard = serviceWorker.indexOf("response.type === 'opaqueredirect'")
  const bodyRead = serviceWorker.indexOf('response.arrayBuffer()')

  assert.ok(redirectGuard >= 0)
  assert.ok(bodyRead >= 0)
  assert.ok(redirectGuard < bodyRead)
  assert.match(serviceWorker, /vera-fidei-pwa-v15/)
})

test('the public root renders the presentation without a navigation redirect', () => {
  assert.match(homePage, /export \{ default \} from ['"]\.\/apresentacao\/page['"]/)
  assert.doesNotMatch(homePage, /\bredirect\s*\(/)
})
