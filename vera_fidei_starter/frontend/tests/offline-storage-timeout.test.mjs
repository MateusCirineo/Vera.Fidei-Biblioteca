import assert from 'node:assert/strict'
import test from 'node:test'

import { getOfflineBooks } from '../lib/offlineBooks.ts'

async function withIndexedDb(indexedDb, callback, timers = null) {
  const previousIndexedDb = Object.getOwnPropertyDescriptor(globalThis, 'indexedDB')
  const previousSetTimeout = globalThis.setTimeout
  const previousClearTimeout = globalThis.clearTimeout

  Object.defineProperty(globalThis, 'indexedDB', {
    configurable: true,
    value: indexedDb,
  })
  if (timers) {
    globalThis.setTimeout = timers.setTimeout
    globalThis.clearTimeout = timers.clearTimeout
  }

  try {
    return await callback()
  } finally {
    if (previousIndexedDb) Object.defineProperty(globalThis, 'indexedDB', previousIndexedDb)
    else delete globalThis.indexedDB
    globalThis.setTimeout = previousSetTimeout
    globalThis.clearTimeout = previousClearTimeout
  }
}

function pendingOpenRequest() {
  return {
    result: null,
    error: null,
    onupgradeneeded: null,
    onblocked: null,
    onsuccess: null,
    onerror: null,
  }
}

test('encerra a abertura do IndexedDB quando outra aba bloqueia a operação', async () => {
  await withIndexedDb({
    open() {
      const request = pendingOpenRequest()
      queueMicrotask(() => request.onblocked?.())
      return request
    },
  }, async () => {
    await assert.rejects(
      getOfflineBooks(),
      /armazenamento offline está bloqueado por outra aba/i,
    )
  })
})

test('aplica deadline determinístico quando a abertura do IndexedDB não responde', async () => {
  const immediateTimers = {
    setTimeout(callback) {
      queueMicrotask(callback)
      return 1
    },
    clearTimeout() {},
  }

  await withIndexedDb({
    open: () => pendingOpenRequest(),
  }, async () => {
    await assert.rejects(
      getOfflineBooks(),
      /armazenamento offline demorou demais para abrir/i,
    )
  }, immediateTimers)
})

test('trata aborto da transação sem retornar dados parcialmente gravados', async () => {
  const transaction = {
    error: null,
    oncomplete: null,
    onerror: null,
    onabort: null,
    abort() {},
    objectStore() {
      return {
        getAll() {
          const request = { result: [], error: null, onsuccess: null, onerror: null }
          queueMicrotask(() => transaction.onabort?.())
          return request
        },
      }
    },
  }
  const db = {
    transaction: () => transaction,
  }

  await withIndexedDb({
    open() {
      const request = pendingOpenRequest()
      request.result = db
      queueMicrotask(() => request.onsuccess?.())
      return request
    },
  }, async () => {
    await assert.rejects(
      getOfflineBooks(),
      /operação offline foi interrompida com segurança/i,
    )
  })
})
