'use client'

import { useState } from 'react'
import Link from 'next/link'
import type { Book } from '@/lib/types'
import { formatLanguage } from '@/lib/language'

function sourceNameFor(book: Book): string {
  return book.source_label || book.edition_label || 'Fonte cadastrada'
}

function referenceLineFor(book: Book): string {
  return [
    book.author,
    book.title,
    book.edition_label || book.source_label,
    book.document_year,
  ]
    .filter(Boolean)
    .join(' — ')
}

function metaValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

export default function BookDetail({ book }: { book: Book }) {
  const [copied, setCopied] = useState(false)
  const hasPdf = (book.files?.length ?? 0) > 0
  const isIndexed = (book.chunk_count ?? 0) > 0
  const sourceName = sourceNameFor(book)
  const referenceLine = referenceLineFor(book)
  const referenceItems = [
    { label: 'Origem', value: sourceName },
    { label: 'Arquivo', value: hasPdf ? `${book.files!.length} PDF vinculado` : 'sem PDF local' },
    { label: 'Indexação', value: isIndexed ? `${book.chunk_count?.toLocaleString('pt-BR')} trechos` : 'aguardando trechos' },
  ]
  const metadata = [
    { label: 'Coleção', value: book.collection },
    { label: 'Idioma', value: book.language ? formatLanguage(book.language) : null },
    { label: 'Edição', value: book.edition_label },
    { label: 'Fonte', value: book.source_label },
    { label: 'Papa', value: book.pope },
    { label: 'Ano', value: book.document_year },
    { label: 'Status', value: book.document_status },
    { label: 'Trechos indexados', value: book.chunk_count?.toLocaleString('pt-BR') },
  ].filter(item => item.value !== null && item.value !== undefined && item.value !== '')

  async function copyReference() {
    await navigator.clipboard.writeText(referenceLine || book.title)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  }

  return (
    <div className="space-y-6">
      <div className="border-b border-fundo-borda pb-4">
        <Link
          href="/biblioteca"
          className="mb-3 inline-flex items-center gap-1 text-xs text-texto-terciario transition-colors hover:text-dourado"
        >
          <span aria-hidden="true">‹</span>
          Biblioteca
        </Link>
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
              Ficha de fonte
            </p>
            <h1 className="mt-1 font-garamond text-3xl font-semibold leading-tight text-texto">
              {book.title}
            </h1>
            {book.author && (
              <p className="mt-1 text-base text-texto-secundario">{book.author}</p>
            )}
          </div>
          <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${
            book.is_primary_source
              ? 'bg-dourado/15 text-dourado'
              : 'bg-fundo-card text-texto-terciario'
          }`}>
            {book.is_primary_source ? 'Fonte primária' : 'Material de apoio'}
          </span>
        </div>
      </div>

      <section className="rounded-lg border border-dourado/20 bg-dourado/5 px-4 py-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
              Referência da obra
            </p>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-texto-secundario">
              {referenceLine || 'Obra catalogada no acervo Vera.Fidei.'}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <button
              type="button"
              onClick={copyReference}
              className="rounded-md border border-dourado/35 px-3 py-1.5 text-xs font-medium text-dourado transition-colors hover:bg-dourado/10"
            >
              {copied ? 'Copiada' : 'Copiar referência'}
            </button>
            <Link
              href="/verificador"
              className="rounded-md border border-fundo-borda px-3 py-1.5 text-xs font-medium text-texto-secundario transition-colors hover:border-dourado/30 hover:text-texto"
            >
              Verificar citação
            </Link>
          </div>
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          {referenceItems.map(item => (
            <div key={item.label} className="border-l border-fundo-borda pl-3">
              <p className="text-xs text-texto-terciario">{item.label}</p>
              <p className="mt-0.5 text-sm leading-snug text-texto">{item.value}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
        <div className="mb-3 flex items-center justify-between gap-3 border-b border-fundo-borda pb-3">
          <div>
            <h2 className="font-garamond text-xl font-medium text-texto">
              Dados editoriais
            </h2>
            <p className="text-xs text-texto-terciario">
              Metadados usados para estudo, busca e verificação.
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
          {metadata.map(item => (
            <div key={item.label} className="rounded-md border border-fundo-borda bg-fundo px-3 py-2">
              <p className="mb-0.5 text-xs uppercase tracking-wider text-texto-terciario">
                {item.label}
              </p>
              <p className="text-texto">{metaValue(item.value)}</p>
            </div>
          ))}
        </div>
      </section>

      {book.files && book.files.length > 0 && (
        <section>
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h2 className="font-garamond text-xl font-medium text-texto">
                Arquivos / Edições
              </h2>
              <p className="text-xs text-texto-terciario">
                Leitura direta pelo visualizador do Vera.Fidei.
              </p>
            </div>
            <span className="rounded-full bg-dourado/15 px-2.5 py-1 text-xs font-medium text-dourado">
              {book.files.length}
            </span>
          </div>
          <div className="space-y-3">
            {book.files.map((file) => (
              <div
                key={file.id}
                className="flex items-start justify-between gap-3 rounded-lg border border-fundo-borda bg-fundo-card p-4"
              >
                <div className="min-w-0 space-y-1">
                  <p className="truncate text-sm text-texto">
                    {file.original_filename}
                  </p>
                  <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-texto-terciario">
                    {file.volume_number && <span>Vol. {file.volume_number}</span>}
                    {file.editor && <span>Ed. {file.editor}</span>}
                    {file.translator && <span>Trad. {file.translator}</span>}
                    <span>{new Date(file.created_at).toLocaleDateString('pt-BR')}</span>
                  </div>
                </div>
                <Link
                  href={`/visualizar/${file.id}`}
                  className="shrink-0 rounded-md border border-dourado/50 px-3 py-1.5 text-xs font-medium text-dourado transition-colors hover:bg-dourado/10"
                >
                  Ler PDF
                </Link>
              </div>
            ))}
          </div>
        </section>
      )}

      {(!book.files || book.files.length === 0) && (
        <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
          <p className="text-sm text-texto-terciario">
            {book.source_label === 'Vatican.va'
              ? 'Documento disponível em Vatican.va; conteúdo indexado para busca e verificação.'
              : 'Nenhum arquivo PDF vinculado ainda.'}
          </p>
        </div>
      )}
    </div>
  )
}
