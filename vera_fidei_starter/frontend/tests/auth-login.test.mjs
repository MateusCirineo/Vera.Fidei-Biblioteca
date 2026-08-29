import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { AUTH_STATE_CHANGED_EVENT, login } from '../lib/auth.ts'

const LOGIN_URL = '/api/auth/web-login'
const ME_URL = '/api/auth/me'

async function withBrowserEnvironment(fetchImplementation, callback, timers = null) {
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
  const previousFetch = globalThis.fetch
  const previousSetTimeout = globalThis.setTimeout
  const previousClearTimeout = globalThis.clearTimeout
  const events = []

  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: {
      location: { origin: 'https://verafidei.oialfred.com' },
      dispatchEvent(event) {
        events.push(event)
        return true
      },
    },
  })
  globalThis.fetch = fetchImplementation
  if (timers) {
    globalThis.setTimeout = timers.setTimeout
    globalThis.clearTimeout = timers.clearTimeout
  }

  try {
    return await callback(events)
  } finally {
    if (previousWindow) Object.defineProperty(globalThis, 'window', previousWindow)
    else delete globalThis.window
    globalThis.fetch = previousFetch
    globalThis.setTimeout = previousSetTimeout
    globalThis.clearTimeout = previousClearTimeout
  }
}

test('confirma /auth/me antes de anunciar o login para a interface', async () => {
  const requests = []
  const expectedUser = {
    id: 17,
    name: 'Leitor Fiel',
    email: 'leitor@example.com',
    plan: 'fiel',
    is_active: true,
    avatar_url: '/api/auth/avatar?v=1',
  }

  await withBrowserEnvironment(async (url, init = {}) => {
    requests.push({ url: String(url), init })
    if (String(url) === LOGIN_URL) {
      return new Response(JSON.stringify({ authenticated: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    assert.equal(String(url), ME_URL)
    return new Response(JSON.stringify(expectedUser), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }, async (events) => {
    const user = await login('leitor@example.com', 'senha-segura')

    assert.equal(user.id, expectedUser.id)
    assert.equal(user.plan, 'fiel')
    assert.equal(user.avatar_url, 'https://verafidei.oialfred.com/api/auth/avatar?v=1')
    assert.deepEqual(requests.map(request => request.url), [LOGIN_URL, ME_URL])
    assert.equal(requests.every(request => request.init.credentials === 'include'), true)
    assert.deepEqual(events.map(event => event.type), [AUTH_STATE_CHANGED_EVENT])
  })
})

test('HTTP 200 sem sessão confirmada falha visivelmente e não anuncia login', async () => {
  await withBrowserEnvironment(async (url) => {
    if (String(url) === LOGIN_URL) {
      return new Response(JSON.stringify({ authenticated: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    return new Response(JSON.stringify({ detail: 'Token ausente.' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    })
  }, async (events) => {
    await assert.rejects(
      login('leitor@example.com', 'senha-segura'),
      /sessão não pôde ser confirmada/i,
    )
    assert.equal(events.length, 0)
  })
})

test('requisição pendente é abortada com uma mensagem acionável', async () => {
  const immediateTimers = {
    setTimeout(callback) {
      queueMicrotask(callback)
      return 1
    },
    clearTimeout() {},
  }

  await withBrowserEnvironment((_url, init = {}) => new Promise((_resolve, reject) => {
    init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
  }), async (events) => {
    await assert.rejects(
      login('leitor@example.com', 'senha-segura'),
      /login demorou demais/i,
    )
    assert.equal(events.length, 0)
  }, immediateTimers)
})

test('a página navega de forma determinística e mostra confirmação', () => {
  const source = readFileSync(new URL('../app/login/page.tsx', import.meta.url), 'utf8')

  assert.match(source, /window\.location\.replace\(redirect\)/)
  assert.match(source, /Conta confirmada\. Abrindo seu perfil/)
  assert.match(source, /role="status"/)
  assert.doesNotMatch(source, /router\.refresh\(\)/)
})
