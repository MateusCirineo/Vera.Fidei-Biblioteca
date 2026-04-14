import { listBooks, listAuthorsCatalog } from '@/lib/api'
import type { Book, AuthorCatalogEntry } from '@/lib/types'
import LibraryView from '@/components/biblioteca/LibraryView'

export default async function BibliotecaPage() {
  let books: Book[] = []
  let catalog: AuthorCatalogEntry[] = []
  let fetchError = false

  try {
    ;[books, catalog] = await Promise.all([listBooks(), listAuthorsCatalog()])
  } catch {
    fetchError = true
  }

  return (
    <div className="mx-auto max-w-2xl px-4 pt-8 pb-24">
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
        <LibraryView books={books} catalog={catalog} />
      )}
    </div>
  )
}
