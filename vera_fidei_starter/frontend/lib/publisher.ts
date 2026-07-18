import type { Book } from './types'

export const ALL_PUBLISHERS = 'todas'
export const UNKNOWN_PUBLISHER = 'Outras editoras'

export const COLLECTION_LABEL: Record<string, string> = {
  PT: 'Paulus',
  PL: 'Migne PL',
  PG: 'Migne PG',
  PO: 'Patrologia Orientalis',
}

export type PublisherTab = {
  id: string
  label: string
  count: number
}

export function normalizePublisherId(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

function normalizeText(value: string | null | undefined): string {
  return (value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
}

function canonicalPublisherLabel(label: string): string {
  const normalized = normalizeText(label)
  if (normalized.includes('ecclesia')) return 'Ecclesiae'
  if (normalized.includes('loyola')) return 'Loyola'
  if (normalized.includes('paulus')) return 'Paulus'
  if (normalized.includes('permanencia')) return 'Permanência'
  if (normalized.includes('vozes')) return 'Vozes'
  if (normalized.includes('wmf martins fontes') || normalized.includes('martins fontes')) return 'WMF Martins Fontes'
  if (normalized.includes('ave maria')) return 'Ave-Maria'
  if (normalized.includes('unesp')) return 'Editora UNESP'
  if (normalized.includes('concreta')) return 'Concreta'
  if (normalized.includes('yale university press')) return 'Yale University Press'
  if (normalized.includes('rodopi')) return 'Rodopi'
  if (normalized.includes('familia catolica')) return 'Editora Família Católica'
  if (normalized.includes('jacques') || normalized.includes('migne')) return label.trim()
  return label.trim()
}

function isRealPublisher(label: string | null | undefined, book: Book, author?: string | null): label is string {
  const clean = label?.trim()
  if (!clean) return false

  const normalized = normalizeText(clean)
  if (!normalized || normalized.startsWith('google drive')) return false
  if (normalized === normalizeText(UNKNOWN_PUBLISHER)) return false
  if (['doc', 'pt', 'pdf', 'obra catalogada', 'fonte primaria'].includes(normalized)) return false
  if (author && normalized === normalizeText(author)) return false
  if (normalized === normalizeText(book.title) || normalized === normalizeText(book.canonical_title)) return false
  if (/^(santo|santa|sao|beato|beata)\b/.test(normalized) && !normalized.includes('editora')) return false
  return true
}

export function publisherForBook(book: Book, author?: string | null): string {
  const fileEditor = book.files
    ?.map(file => file.editor)
    .find(label => isRealPublisher(label, book, author))

  if (fileEditor) return canonicalPublisherLabel(fileEditor)
  if (isRealPublisher(book.edition_label, book, author)) return canonicalPublisherLabel(book.edition_label)
  if (book.collection && COLLECTION_LABEL[book.collection]) return COLLECTION_LABEL[book.collection]
  return UNKNOWN_PUBLISHER
}

export function publisherTabsForBooks(books: Book[], author?: string | null): PublisherTab[] {
  const counts = new Map<string, PublisherTab>()
  for (const book of books) {
    const label = publisherForBook(book, author)
    const id = normalizePublisherId(label)
    const current = counts.get(id)
    if (current) {
      current.count += 1
    } else {
      counts.set(id, { id, label, count: 1 })
    }
  }

  return [...counts.values()].sort((a, b) => {
    if (a.label === UNKNOWN_PUBLISHER) return 1
    if (b.label === UNKNOWN_PUBLISHER) return -1
    return a.label.localeCompare(b.label, 'pt')
  })
}

export function publisherSummary(books: Book[], author?: string | null): string {
  const labels = [...new Set(books.map(book => publisherForBook(book, author)).filter(Boolean))]
  return labels.length > 0 ? labels.join(' · ') : UNKNOWN_PUBLISHER
}
