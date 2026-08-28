import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { RequestTimeoutError, fetchWithTimeout } from '../lib/http.ts'

async function withFetch(fetchImplementation, callback, timers = null) {
  const previousFetch = globalThis.fetch
  const previousSetTimeout = globalThis.setTimeout
  const previousClearTimeout = globalThis.clearTimeout
  globalThis.fetch = fetchImplementation
  if (timers) {
    globalThis.setTimeout = timers.setTimeout
    globalThis.clearTimeout = timers.clearTimeout
  }

  try {
    return await callback()
  } finally {
    globalThis.fetch = previousFetch
    globalThis.setTimeout = previousSetTimeout
    globalThis.clearTimeout = previousClearTimeout
  }
}

const immediateTimers = {
  setTimeout(callback) {
    queueMicrotask(callback)
    return 1
  },
  clearTimeout() {},
}

test('aborta uma requisição que não entrega os cabeçalhos', async () => {
  await withFetch((_url, init = {}) => new Promise((_resolve, reject) => {
    init.signal?.addEventListener('abort', () => {
      reject(new DOMException('Aborted', 'AbortError'))
    })
  }), async () => {
    await assert.rejects(
      fetchWithTimeout('https://example.test/pendente', {}, {
        timeoutMs: 10,
        timeoutMessage: 'Tempo de teste excedido.',
      }),
      (error) => error instanceof RequestTimeoutError
        && error.status === 408
        && error.message === 'Tempo de teste excedido.',
    )
  }, immediateTimers)
})

test('encerra também quando os cabeçalhos chegam mas json() nunca termina', async () => {
  await withFetch(async () => {
    const response = new Response('{}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
    Object.defineProperty(response, 'json', {
      configurable: true,
      value: () => new Promise(() => {}),
    })
    return response
  }, async () => {
    const response = await fetchWithTimeout('https://example.test/corpo-pendente', {}, {
      timeoutMs: 10,
      timeoutMessage: 'O corpo da resposta demorou demais.',
    })
    await assert.rejects(response.json(), (error) => (
      error instanceof RequestTimeoutError
      && error.status === 408
      && error.message === 'O corpo da resposta demorou demais.'
    ))
  }, immediateTimers)
})

test('preserva o cancelamento solicitado pelo chamador', async () => {
  const parent = new AbortController()
  await withFetch((_url, init = {}) => new Promise((_resolve, reject) => {
    init.signal?.addEventListener('abort', () => {
      reject(new DOMException('Aborted', 'AbortError'))
    })
  }), async () => {
    const request = fetchWithTimeout('https://example.test/cancelada', {
      signal: parent.signal,
    }, { timeoutMs: 5_000 })
    parent.abort()

    await assert.rejects(
      request,
      (error) => error instanceof DOMException && error.name === 'AbortError',
    )
  })
})

test('mantém a resposta normal e permite consumir o corpo', async () => {
  await withFetch(async () => new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  }), async () => {
    const response = await fetchWithTimeout('https://example.test/sucesso', {}, {
      timeoutMs: 1_000,
    })
    assert.deepEqual(await response.json(), { ok: true })
  })
})

test('os formulários críticos sempre encerram seus estados de carregamento', () => {
  const cadastro = readFileSync(new URL('../app/cadastro/page.tsx', import.meta.url), 'utf8')
  const verificador = readFileSync(
    new URL('../components/verificador/VerificationForm.tsx', import.meta.url),
    'utf8',
  )
  const planos = readFileSync(new URL('../app/planos/page.tsx', import.meta.url), 'utf8')

  assert.match(cadastro, /finally\s*\{\s*setLoading\(false\)/s)
  assert.match(verificador, /finally\s*\{\s*setLoading\(false\)/s)
  assert.match(planos, /finally\s*\{\s*setBusyPlan\(''\)/s)
})

test('a primeira página do PDF compartilha timeout e cancelamento do carregamento', () => {
  const viewer = readFileSync(new URL('../app/viewer/pdf/page.tsx', import.meta.url), 'utf8')

  assert.match(
    viewer,
    /firstPage\s*=\s*await Promise\.race\(\[doc\.getPage\(1\), timeoutPromise, cancelledPromise\]\)/,
  )
  assert.match(viewer, /loadController\.abort\(\)/)
})

test('páginas posteriores limitam getPage, render e getTextContent e exibem falha recuperável', () => {
  const viewer = readFileSync(new URL('../app/viewer/pdf/page.tsx', import.meta.url), 'utf8')

  assert.match(viewer, /Promise\.race\(\[pdfDoc\.getPage\(pageNum\), interrupted\]\)/)
  assert.match(viewer, /Promise\.race\(\[currentRenderTask\.promise, interrupted\]\)/)
  assert.match(viewer, /Promise\.race\(\[page\.getTextContent\(\), interrupted\]\)/)
  assert.match(viewer, /role="alert"/)
  assert.match(viewer, /Tentar novamente/)
})

test('proxy limita o corpo de erro e telemetria fire-and-forget usa o helper central', () => {
  const proxy = readFileSync(
    new URL('../app/api/pdfs/[fileId]/route.ts', import.meta.url),
    'utf8',
  )
  const analytics = readFileSync(
    new URL('../components/SiteAnalytics.tsx', import.meta.url),
    'utf8',
  )

  assert.match(proxy, /PDF_UPSTREAM_ERROR_BODY_TIMEOUT_MS/)
  assert.match(proxy, /Promise\.race\(\[response\.text\(\), timeout\]\)/)
  assert.match(analytics, /fetchWithTimeout\(/)
  assert.match(analytics, /ANALYTICS_TIMEOUT_MS/)
  assert.match(analytics, /response\.text\(\)/)
})
