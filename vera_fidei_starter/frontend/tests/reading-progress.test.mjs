import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  buildTrackedViewerHref,
  clearLocalReadingProgress,
  extractBookFileId,
  flushPendingReadingProgress,
  localReadingProgressKey,
  readLocalReadingProgress,
  saveReadingProgress,
  syncReadingProgressWithFallback,
  writeLocalReadingProgress,
} from '../lib/readingProgress.ts'

function memoryStorage() {
  const values = new Map()
  return {
    get length() { return values.size },
    getItem(key) { return values.get(key) ?? null },
    setItem(key, value) { values.set(key, String(value)) },
    removeItem(key) { values.delete(key) },
    key(index) { return [...values.keys()][index] ?? null },
    clear() { values.clear() },
  }
}

function remoteProgress({ page, revision, completed = false, endPage = 100 }) {
  return {
    book_id: 20,
    book_file_id: 30,
    current_page: page,
    total_pages: 100,
    progress_percent: endPage === null ? null : page,
    first_opened_at: '2026-08-29T00:00:00Z',
    last_read_at: `2026-08-29T00:${String(revision).padStart(2, '0')}:00Z`,
    completed,
    revision,
    start_page: 1,
    end_page: endPage,
    viewer_href: `/viewer/pdf?file=%2Fapi%2Fpdfs%2F30&book=20&page=${page}&reading=1`,
    book: { id: 20, title: 'Obra', author: null, collection: null, language: null, edition_label: null, canonical_title: null, canonical_author: null },
    file: { id: 30, original_filename: 'obra.pdf', volume_number: null, editor: null, translator: null },
  }
}

test('particiona o fallback por conta, obra logica e arquivo fisico', () => {
  assert.notEqual(
    localReadingProgressKey(10, 20, 30),
    localReadingProgressKey(11, 20, 30),
  )
  assert.notEqual(
    localReadingProgressKey(10, 20, 30),
    localReadingProgressKey(10, 21, 30),
  )

  const previousWindow = globalThis.window
  globalThis.window = { localStorage: memoryStorage() }
  try {
    writeLocalReadingProgress(10, 20, 30, {
      current_page: 17,
      total_pages: 100,
      event: 'progress',
    })
    const saved = readLocalReadingProgress(10, 20, 30)
    assert.equal(saved?.current_page, 17)
    assert.equal(new URL(saved.viewer_href, 'https://verafidei.test').searchParams.get('page'), '17')
    assert.equal(readLocalReadingProgress(11, 20, 30), null)
    assert.equal(readLocalReadingProgress(10, 21, 30), null)
  } finally {
    globalThis.window = previousWindow
  }
})

test('gera URL rastreada e extrai apenas ids validos do proxy de PDF', () => {
  const href = buildTrackedViewerHref(58, 1742, 12)
  const params = new URL(href, 'https://verafidei.test').searchParams
  assert.equal(params.get('file'), '/api/pdfs/58')
  assert.equal(params.get('book'), '1742')
  assert.equal(params.get('page'), '12')
  assert.equal(params.get('reading'), '1')
  assert.equal(extractBookFileId('/api/pdfs/58'), 58)
  assert.equal(extractBookFileId('https://verafidei.com.br/api/pdfs/58?download=0'), 58)
  assert.equal(extractBookFileId('javascript:alert(1)'), null)
})

test('envia a obra logica junto do arquivo ao salvar no backend', async () => {
  const previousFetch = globalThis.fetch
  let capturedUrl = ''
  let capturedBody = null
  globalThis.fetch = async (input, init = {}) => {
    capturedUrl = String(input)
    capturedBody = JSON.parse(String(init.body))
    return new Response(JSON.stringify({
      book_id: 20,
      book_file_id: 30,
      current_page: 17,
      total_pages: 100,
      progress_percent: 17,
      first_opened_at: '2026-08-29T00:00:00Z',
      last_read_at: '2026-08-29T00:01:00Z',
      completed: false,
      revision: 1,
      start_page: 1,
      end_page: 100,
      viewer_href: '/viewer/pdf',
      book: { id: 20, title: 'Obra', author: null, collection: null, language: null, edition_label: null, canonical_title: null, canonical_author: null },
      file: { id: 30, original_filename: 'obra.pdf', volume_number: null, editor: null, translator: null },
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }

  try {
    await saveReadingProgress(30, 20, {
      current_page: 17,
      total_pages: 100,
      event: 'progress',
    })
    assert.equal(new URL(capturedUrl).searchParams.get('book_id'), '20')
    assert.deepEqual(capturedBody, {
      book_id: 20,
      current_page: 17,
      total_pages: 100,
      event: 'progress',
    })
  } finally {
    globalThis.fetch = previousFetch
  }
})

test('serializa escritas e preserva a pagina mais nova enquanto a anterior responde', async () => {
  const previousWindow = globalThis.window
  const previousFetch = globalThis.fetch
  globalThis.window = { localStorage: memoryStorage() }

  let releaseFirstPut
  let signalFirstPut
  const firstPutStarted = new Promise((resolve) => { signalFirstPut = resolve })
  const releaseFirst = new Promise((resolve) => { releaseFirstPut = resolve })
  const bodies = []
  let inFlight = 0
  let maxInFlight = 0

  globalThis.fetch = async (_input, init = {}) => {
    if ((init.method || 'GET') === 'GET') return new Response(null, { status: 404 })
    const body = JSON.parse(String(init.body))
    bodies.push(body)
    inFlight += 1
    maxInFlight = Math.max(maxInFlight, inFlight)
    if (bodies.length === 1) {
      signalFirstPut()
      await releaseFirst
    }
    const response = remoteProgress({ page: body.current_page, revision: bodies.length })
    inFlight -= 1
    return new Response(JSON.stringify(response), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  try {
    const first = syncReadingProgressWithFallback(10, 20, 30, {
      current_page: 10,
      total_pages: 100,
      event: 'progress',
    })
    await firstPutStarted
    const second = syncReadingProgressWithFallback(10, 20, 30, {
      current_page: 20,
      total_pages: 100,
      event: 'progress',
    })
    releaseFirstPut()
    await Promise.all([first, second])

    assert.equal(maxInFlight, 1)
    assert.deepEqual(bodies.map((body) => body.current_page), [10, 20])
    assert.equal(bodies[1].base_revision, 1)
    assert.equal(readLocalReadingProgress(10, 20, 30)?.current_page, 20)
    assert.equal(readLocalReadingProgress(10, 20, 30)?.revision, 2)
    assert.equal(readLocalReadingProgress(10, 20, 30)?.pending_sync, false)
  } finally {
    globalThis.fetch = previousFetch
    globalThis.window = previousWindow
  }
})

test('reconcilia pendencia com GET e nao sobrescreve revision remota mais nova', async () => {
  const previousWindow = globalThis.window
  const previousFetch = globalThis.fetch
  globalThis.window = { localStorage: memoryStorage() }
  writeLocalReadingProgress(12, 20, 30, {
    current_page: 20,
    total_pages: 100,
    event: 'progress',
  }, { pendingSync: true, revision: 1 })

  let putCount = 0
  globalThis.fetch = async (_input, init = {}) => {
    if ((init.method || 'GET') === 'PUT') putCount += 1
    return new Response(JSON.stringify(remoteProgress({ page: 30, revision: 2 })), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  try {
    const result = await flushPendingReadingProgress(12)
    const local = readLocalReadingProgress(12, 20, 30)
    assert.equal(putCount, 0)
    assert.equal(local?.current_page, 30)
    assert.equal(local?.revision, 2)
    assert.equal(local?.pending_sync, false)
    assert.deepEqual(result, { attempted: 1, synced: 1, remaining: 0 })
  } finally {
    globalThis.fetch = previousFetch
    globalThis.window = previousWindow
  }
})

test('reabrir offline preserva a pagina pendente antes de registrar open', async () => {
  const previousWindow = globalThis.window
  const previousFetch = globalThis.fetch
  globalThis.window = { localStorage: memoryStorage() }
  writeLocalReadingProgress(13, 20, 30, {
    current_page: 47,
    total_pages: 100,
    event: 'progress',
  }, { pendingSync: true, revision: 3 })
  globalThis.fetch = async () => {
    throw new TypeError('offline')
  }

  try {
    const result = await syncReadingProgressWithFallback(13, 20, 30, {
      current_page: 47,
      total_pages: 100,
      event: 'open',
    })
    const local = readLocalReadingProgress(13, 20, 30)

    assert.equal(result.current_page, 47)
    assert.equal(local?.current_page, 47)
    assert.equal(local?.event, 'progress')
    assert.equal(local?.revision, 3)
    assert.equal(local?.pending_sync, true)
  } finally {
    globalThis.fetch = previousFetch
    globalThis.window = previousWindow
  }
})

test('limpar a conta invalida resposta de sincronizacao que ainda estava em voo', async () => {
  const previousWindow = globalThis.window
  const previousFetch = globalThis.fetch
  globalThis.window = { localStorage: memoryStorage() }

  let releasePut
  let signalPut
  const putStarted = new Promise((resolve) => { signalPut = resolve })
  const release = new Promise((resolve) => { releasePut = resolve })
  globalThis.fetch = async (_input, init = {}) => {
    if ((init.method || 'GET') === 'GET') return new Response(null, { status: 404 })
    signalPut()
    await release
    return new Response(JSON.stringify(remoteProgress({ page: 40, revision: 1 })), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  try {
    const syncing = syncReadingProgressWithFallback(14, 20, 30, {
      current_page: 40,
      total_pages: 100,
      event: 'progress',
    })
    await putStarted
    assert.equal(clearLocalReadingProgress(14), 1)
    releasePut()
    await syncing
    assert.equal(readLocalReadingProgress(14, 20, 30), null)
  } finally {
    globalThis.fetch = previousFetch
    globalThis.window = previousWindow
  }
})

test('viewer salva somente leitura explicita, com debounce e flush de saida', () => {
  const viewer = readFileSync(new URL('../app/viewer/pdf/page.tsx', import.meta.url), 'utf8')
  const helper = readFileSync(new URL('../lib/readingProgress.ts', import.meta.url), 'utf8')

  assert.match(viewer, /searchParams\.get\('reading'\) === '1'/)
  assert.match(viewer, /persistReadingPage\('open', false, initialPage\)/)
  assert.match(viewer, /setTimeout\(\(\) => \{[\s\S]*persistReadingPage\('progress'\)[\s\S]*\}, 1_500\)/)
  assert.match(viewer, /document\.addEventListener\('visibilitychange'/)
  assert.match(viewer, /window\.addEventListener\('pagehide'/)
  assert.match(viewer, /openedReadingSessionRef\.current\.startsWith\(identity\)/)
  assert.match(viewer, /openedReadingSessionRef\.current = ''/)
  assert.match(viewer, /onClick=\{leaveViewer\}/g)
  assert.doesNotMatch(viewer, /onClick=\{\(\) => router\.back\(\)\}/)
  assert.match(helper, /const readingSyncQueues = new Map/)
  assert.match(helper, /previous[\s\S]*\.then\(\(\) => syncPendingLocalProgress/)
})

test('detalhe e biblioteca apresentam retomada sem alterar links de citacao', () => {
  const detail = readFileSync(
    new URL('../components/biblioteca/BookDetail.tsx', import.meta.url),
    'utf8',
  )
  const library = readFileSync(new URL('../app/biblioteca/page.tsx', import.meta.url), 'utf8')
  const card = readFileSync(
    new URL('../components/biblioteca/ContinueReadingCard.tsx', import.meta.url),
    'utf8',
  )

  assert.match(detail, /buildTrackedViewerHref\(file\.id, book\.id, resumePage\)/)
  assert.match(detail, /Continuar lendo/)
  assert.match(detail, /Recomeçar/)
  assert.match(library, /<ContinueReadingCard \/>/)
  assert.match(card, /find\(\(candidate\) => !isCompleted\(candidate\)\)/)
  assert.match(card, /percent !== null/)
  assert.doesNotMatch(card, /page \/ totalPages/)
})
