import { getBook } from '@/lib/api'
import BookDetail from '@/components/biblioteca/BookDetail'
import Link from 'next/link'
import { notFound } from 'next/navigation'

export default async function BookPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const bookId = parseInt(id, 10)

  if (isNaN(bookId)) notFound()

  let book
  try {
    book = await getBook(bookId)
  } catch {
    notFound()
  }

  return (
    <div className="mx-auto max-w-2xl px-4 pt-6 pb-4">
      <Link
        href="/biblioteca"
        className="inline-flex items-center gap-1.5 text-sm text-texto-secundario hover:text-texto mb-5"
      >
        <svg
          viewBox="0 0 20 20"
          fill="currentColor"
          className="w-4 h-4"
        >
          <path
            fillRule="evenodd"
            d="M17 10a.75.75 0 0 1-.75.75H5.612l4.158 3.96a.75.75 0 1 1-1.04 1.08l-5.5-5.25a.75.75 0 0 1 0-1.08l5.5-5.25a.75.75 0 1 1 1.04 1.08L5.612 9.25H16.25A.75.75 0 0 1 17 10Z"
            clipRule="evenodd"
          />
        </svg>
        Biblioteca
      </Link>
      <BookDetail book={book} />
    </div>
  )
}
