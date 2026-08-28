'use client'

import { LONG_REQUEST_TIMEOUT_MS, fetchWithTimeout } from './http.ts'

// Armazena texto de trechos já extraídos em IndexedDB.
// Nunca faz download do arquivo PDF — só o conteúdo textual já indexado.

const DB_NAME = 'vera-fidei-offline'
const DB_VERSION = 1
const STORE = 'books'
const OFFLINE_DB_TIMEOUT_MS = 10_000

function offlineStorageError(message: string, cause?: unknown): Error {
  const error = new Error(message, cause === undefined ? undefined : { cause })
  error.name = 'OfflineStorageError'
  return error
}

export interface OfflineChunk {
  chunk_id: number
  sequence_index: number | null
  chapter_or_section: string | null
  text: string
  translation_pt: string | null
  pdf_page: number | null
  volume: number | null
  source_fidelity: 'verified_transcription' | 'source_text'
  source_fidelity_label: string
}

export interface OfflineBookEntry {
  book_id: number
  title: string
  author: string | null
  edition_label: string | null
  language: string | null
  chunks: OfflineChunk[]
  total_chunks: number
  saved_at: string
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    let settled = false
    const timeoutId = globalThis.setTimeout(() => {
      if (settled) return
      settled = true
      reject(offlineStorageError('O armazenamento offline demorou demais para abrir. Tente novamente.'))
    }, OFFLINE_DB_TIMEOUT_MS)
    const rejectOnce = (error: Error) => {
      if (settled) return
      settled = true
      globalThis.clearTimeout(timeoutId)
      reject(error)
    }
    req.onupgradeneeded = () => {
      req.result.createObjectStore(STORE, { keyPath: 'book_id' })
    }
    req.onblocked = () => rejectOnce(offlineStorageError(
      'O armazenamento offline está bloqueado por outra aba. Feche outras abas do Vera Fidei e tente novamente.',
    ))
    req.onsuccess = () => {
      if (settled) {
        // A abertura terminou depois de o chamador já receber timeout/bloqueio.
        // Esta conexão não tem proprietário; fechá-la evita bloquear upgrades,
        // sem apagar ou modificar qualquer dado persistido.
        req.result.close()
        return
      }
      settled = true
      globalThis.clearTimeout(timeoutId)
      resolve(req.result)
    }
    req.onerror = () => rejectOnce(offlineStorageError(
      'Não foi possível abrir o armazenamento offline.',
      req.error,
    ))
  })
}

function tx<T>(
  db: IDBDatabase,
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  return new Promise((resolve, reject) => {
    let transaction: IDBTransaction
    let req: IDBRequest<T>
    let requestResult: T
    let requestSucceeded = false
    let settled = false
    const finish = (callback: () => void) => {
      if (settled) return
      settled = true
      globalThis.clearTimeout(timeoutId)
      callback()
    }
    const rejectOnce = (error: Error) => finish(() => reject(error))
    const timeoutId = globalThis.setTimeout(() => {
      if (settled) return
      try {
        transaction?.abort()
      } catch {
        // A transação pode já ter terminado entre o deadline e o abort().
      }
      rejectOnce(offlineStorageError(
        'O armazenamento offline demorou demais para responder. Tente novamente.',
      ))
    }, OFFLINE_DB_TIMEOUT_MS)

    try {
      transaction = db.transaction(STORE, mode)
      const store = transaction.objectStore(STORE)
      req = fn(store)
    } catch (error) {
      rejectOnce(offlineStorageError('Não foi possível iniciar a operação offline.', error))
      return
    }

    req.onsuccess = () => {
      requestResult = req.result
      requestSucceeded = true
    }
    req.onerror = () => rejectOnce(offlineStorageError(
      'Não foi possível concluir a operação offline.',
      req.error,
    ))
    transaction.oncomplete = () => {
      if (!requestSucceeded) {
        rejectOnce(offlineStorageError('A operação offline terminou sem retornar um resultado.'))
        return
      }
      finish(() => resolve(requestResult))
    }
    transaction.onerror = () => rejectOnce(offlineStorageError(
      'A operação offline encontrou um erro.',
      transaction.error,
    ))
    transaction.onabort = () => rejectOnce(offlineStorageError(
      'A operação offline foi interrompida com segurança; nenhum dado parcial foi salvo.',
      transaction.error,
    ))
  })
}

export async function getOfflineBooks(): Promise<OfflineBookEntry[]> {
  const db = await openDB()
  return tx<OfflineBookEntry[]>(db, 'readonly', (s) => s.getAll())
}

export async function getOfflineBook(bookId: number): Promise<OfflineBookEntry | undefined> {
  const db = await openDB()
  return tx<OfflineBookEntry | undefined>(db, 'readonly', (s) => s.get(bookId))
}

export async function isBookOffline(bookId: number): Promise<boolean> {
  const db = await openDB()
  const entry = await tx<OfflineBookEntry | undefined>(db, 'readonly', (s) => s.get(bookId))
  return entry !== undefined
}

export async function saveBookOffline(
  bookId: number,
  apiBase: string,
  apiKey: string,
): Promise<OfflineBookEntry> {
  const params = new URLSearchParams({ book_id: String(bookId), limit: '400' })
  const res = await fetchWithTimeout(`${apiBase}/search/book-chunks?${params}`, {
    headers: apiKey ? { 'X-API-Key': apiKey } : {},
  }, {
    timeoutMs: LONG_REQUEST_TIMEOUT_MS,
    timeoutMessage: 'O conteúdo para leitura offline demorou demais. Tente novamente.',
  })
  if (!res.ok) {
    const msg = await res.text().catch(() => `HTTP ${res.status}`)
    throw new Error(msg || `HTTP ${res.status}`)
  }
  const data = await res.json() as OfflineBookEntry
  const entry: OfflineBookEntry = { ...data, saved_at: new Date().toISOString() }
  const db = await openDB()
  await tx(db, 'readwrite', (s) => s.put(entry))
  return entry
}

export async function removeBookOffline(bookId: number): Promise<void> {
  const db = await openDB()
  await tx(db, 'readwrite', (s) => s.delete(bookId))
}
