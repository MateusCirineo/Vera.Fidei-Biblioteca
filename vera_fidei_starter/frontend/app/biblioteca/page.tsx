import { listBooks } from '@/lib/api'
import type { Book } from '@/lib/types'
import BookList from '@/components/biblioteca/BookList'

export default async function BibliotecaPage() {
  let books: Book[] = []
  let fetchError = false

  try {
    books = await listBooks()
  } catch {
    fetchError = true
  }

  return (
    <div className="mx-auto max-w-2xl px-4 pt-8 pb-4">
      <div className="mb-6">
        <h1 className="font-garamond text-3xl font-semibold text-texto">
          Biblioteca
        </h1>
        <p className="mt-1 text-sm text-texto-secundario">
          Acervo de fontes patrísticas, concílios e documentos da Igreja.
        </p>
      </div>

      {fetchError ? (
        <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-4">
          <p className="text-sm text-red-300">
            Não foi possível carregar as obras. Verifique se o backend está
            rodando em{' '}
            <span className="font-mono">
              {process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}
            </span>
            .
          </p>
        </div>
      ) : (
        <BookList books={books} />
      )}
    </div>
  )
}
