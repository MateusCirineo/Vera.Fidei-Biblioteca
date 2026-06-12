import BrandHeader from '@/components/BrandHeader'
import SantosView from '@/components/santos/SantosView'
import { listBooks } from '@/lib/api'
import {
  SAINT_WORK_PROFILES,
  getRomanSaintForDate,
  getUpcomingRomanSaints,
  normalizeText,
} from '@/lib/roman-calendar'
import type { Book } from '@/lib/types'

export const revalidate = 300

function bookSaintSearchText(book: Book): string {
  return normalizeText([
    book.canonical_author,
    book.author,
    book.title,
    book.canonical_title,
  ].filter(Boolean).join(' '))
}

function filterBooksForSaints(books: Book[], todayAliases: string[]): Book[] {
  const aliases = [
    ...todayAliases,
    ...SAINT_WORK_PROFILES.flatMap(profile => profile.aliases),
  ]
    .map(alias => normalizeText(alias))
    .filter(Boolean)

  return books.filter((book) => {
    const haystack = bookSaintSearchText(book)
    return aliases.some(alias => haystack.includes(alias))
  })
}

export default async function SantosPage() {
  const today = getRomanSaintForDate()
  const upcoming = getUpcomingRomanSaints(5)

  let books: Book[] = []
  try {
    books = await listBooks()
  } catch {
    books = []
  }

  const saintBooks = filterBooksForSaints(books, [today.name, ...today.aliases])

  return (
    <div className="mx-auto max-w-2xl px-4 pt-8 pb-4">
      <BrandHeader
        title="Santos"
        description="Santo do dia, calendário romano e obras dos santos já presentes na Biblioteca."
      />

      <SantosView books={saintBooks} today={today} upcoming={upcoming} />
    </div>
  )
}
