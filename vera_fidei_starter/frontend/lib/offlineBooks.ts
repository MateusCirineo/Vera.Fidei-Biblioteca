'use client'

// Armazena texto de trechos já extraídos em IndexedDB.
// Nunca faz download do arquivo PDF — só o conteúdo textual já indexado.

const DB_NAME = 'vera-fidei-offline'
const DB_VERSION = 1
const STORE = 'books'

export interface OfflineChunk {
  chunk_id: number
  sequence_index: number | null
  chapter_or_section: string | null
  text: string
  translation_pt: string | null
  pdf_page: number | null
  volume: number | null
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
    req.onupgradeneeded = () => {
      req.result.createObjectStore(STORE, { keyPath: 'book_id' })
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

function tx<T>(
  db: IDBDatabase,
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE, mode)
    const store = transaction.objectStore(STORE)
    const req = fn(store)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
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
  const res = await fetch(`${apiBase}/search/book-chunks?${params}`, {
    headers: apiKey ? { 'X-API-Key': apiKey } : {},
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
