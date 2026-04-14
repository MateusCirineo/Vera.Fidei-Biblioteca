'use client'

import { useCallback, useEffect, useState } from 'react'
import { listBooks, deleteBook, updateBookFileMeta } from '@/lib/api'
import type { Book, BookFile } from '@/lib/types'

type EditState = {
  fileId: number
  bookId: number
  editor: string
  translator: string
}

export default function BookList() {
  const [books, setBooks] = useState<Book[]>([])
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [editing, setEditing] = useState<EditState | null>(null)
  const [saving, setSaving] = useState(false)
  const [savedFileId, setSavedFileId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listBooks()
      setBooks(data)
    } catch {
      setError('Erro ao carregar livros.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function handleDelete(book: Book) {
    if (!window.confirm(`Excluir "${book.title}" e todos os seus chunks?\nEsta ação não pode ser desfeita.`)) {
      return
    }
    setDeletingId(book.id)
    setError(null)
    try {
      await deleteBook(book.id)
      setBooks((prev) => prev.filter((b) => b.id !== book.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao excluir livro.')
    } finally {
      setDeletingId(null)
    }
  }

  function openEdit(book: Book, file: BookFile) {
    setEditing({
      fileId: file.id,
      bookId: book.id,
      editor: file.editor ?? '',
      translator: file.translator ?? '',
    })
    setSavedFileId(null)
  }

  function cancelEdit() {
    setEditing(null)
  }

  async function handleSave() {
    if (!editing) return
    setSaving(true)
    try {
      await updateBookFileMeta(
        editing.bookId,
        editing.fileId,
        editing.editor.trim() || null,
        editing.translator.trim() || null,
      )
      // Atualizar localmente para não precisar recarregar
      setBooks((prev) =>
        prev.map((b) => {
          if (b.id !== editing.bookId) return b
          return {
            ...b,
            files: b.files?.map((f) =>
              f.id === editing.fileId
                ? { ...f, editor: editing.editor.trim() || null, translator: editing.translator.trim() || null }
                : f,
            ),
          }
        }),
      )
      setSavedFileId(editing.fileId)
      setEditing(null)
      setTimeout(() => setSavedFileId(null), 2500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-texto-secundario uppercase tracking-wider">
          Acervo indexado
        </h2>
        <button
          onClick={load}
          className="text-xs text-texto-terciario hover:text-texto transition-colors"
        >
          Atualizar
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-400 font-mono">{error}</p>
      )}

      {loading ? (
        <p className="text-sm text-texto-terciario">Carregando...</p>
      ) : books.length === 0 ? (
        <p className="text-sm text-texto-terciario">Nenhum livro indexado.</p>
      ) : (
        <div className="divide-y divide-fundo-borda rounded-lg border border-fundo-borda overflow-hidden">
          {books.map((book) => (
            <div key={book.id} className="bg-fundo-card">
              {/* Linha principal do livro */}
              <div className="flex items-center justify-between gap-4 px-4 py-3 hover:bg-fundo-borda/20 transition-colors">
                <div className="min-w-0">
                  <p className="text-sm text-texto truncate">{book.title}</p>
                  <p className="text-xs text-texto-terciario truncate">
                    {book.canonical_author ?? book.author ?? 'Autor desconhecido'}
                    {book.chunk_count !== undefined && (
                      <span className="ml-2 text-texto-terciario/60">
                        · {book.chunk_count} trecho{book.chunk_count !== 1 ? 's' : ''}
                      </span>
                    )}
                  </p>
                </div>
                <div className="shrink-0 flex items-center gap-3">
                  <button
                    onClick={() => handleDelete(book)}
                    disabled={deletingId === book.id}
                    className="text-xs text-red-400/70 hover:text-red-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    {deletingId === book.id ? 'Excluindo...' : 'Excluir'}
                  </button>
                </div>
              </div>

              {/* Arquivos: editor/tradutor editáveis */}
              {book.files && book.files.length > 0 && (
                <div className="border-t border-fundo-borda/50 px-4 pb-3 pt-2 space-y-2">
                  {book.files.map((file) => (
                    <div key={file.id}>
                      {/* Linha do arquivo */}
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex gap-3 text-xs text-texto-terciario min-w-0">
                          <span>
                            Editora:{' '}
                            <span className="text-texto-secundario">
                              {savedFileId === file.id
                                ? <span className="text-green-400">Salvo!</span>
                                : (file.editor ?? <span className="opacity-50">—</span>)}
                            </span>
                          </span>
                          <span>
                            Tradutor:{' '}
                            <span className="text-texto-secundario">
                              {file.translator ?? <span className="opacity-50">—</span>}
                            </span>
                          </span>
                        </div>
                        <button
                          onClick={() =>
                            editing?.fileId === file.id ? cancelEdit() : openEdit(book, file)
                          }
                          className="shrink-0 text-xs text-texto-terciario hover:text-dourado transition-colors"
                        >
                          {editing?.fileId === file.id ? 'Cancelar' : 'Editar'}
                        </button>
                      </div>

                      {/* Painel de edição inline */}
                      {editing?.fileId === file.id && (
                        <div className="mt-2 space-y-2 rounded-lg border border-dourado/20 bg-fundo-borda/20 p-3">
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="block text-xs text-texto-terciario mb-1">Editora</label>
                              <input
                                type="text"
                                value={editing.editor}
                                onChange={(e) => setEditing({ ...editing, editor: e.target.value })}
                                placeholder="Ex: Paulus"
                                className="w-full rounded border border-fundo-borda bg-fundo-card px-2 py-1.5 text-xs text-texto placeholder:text-texto-terciario focus:outline-none focus:border-dourado/50"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-texto-terciario mb-1">Tradutor</label>
                              <input
                                type="text"
                                value={editing.translator}
                                onChange={(e) => setEditing({ ...editing, translator: e.target.value })}
                                placeholder="Ex: Lourenço Costa"
                                className="w-full rounded border border-fundo-borda bg-fundo-card px-2 py-1.5 text-xs text-texto placeholder:text-texto-terciario focus:outline-none focus:border-dourado/50"
                              />
                            </div>
                          </div>
                          <button
                            onClick={handleSave}
                            disabled={saving}
                            className="rounded bg-dourado/90 hover:bg-dourado disabled:opacity-40 px-3 py-1.5 text-xs font-semibold text-fundo transition-colors"
                          >
                            {saving ? 'Salvando...' : 'Salvar'}
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
