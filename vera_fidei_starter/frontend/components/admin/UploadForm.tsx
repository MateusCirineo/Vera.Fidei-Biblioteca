'use client'

import { useRef, useState, useEffect } from 'react'
import { ingestAuto, getBookStatus, type AutoIngestResult } from '@/lib/api'
import { formatLanguage } from '@/lib/language'

type State =
  | { status: 'idle' }
  | { status: 'uploading' }
  | { status: 'processing'; result: AutoIngestResult }
  | { status: 'done'; result: AutoIngestResult & { chunks_indexed: number } }
  | { status: 'error'; message: string }

export default function UploadForm() {
  const [state, setState] = useState<State>({ status: 'idle' })
  const [title, setTitle] = useState('')
  const [editor, setEditor] = useState('')
  const [translator, setTranslator] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [chunks, setChunks] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Polling de status enquanto está em "processing"
  useEffect(() => {
    if (state.status !== 'processing') {
      if (pollRef.current) clearInterval(pollRef.current)
      return
    }

    const bookId = state.result.id

    pollRef.current = setInterval(async () => {
      try {
        const s = await getBookStatus(bookId)
        setChunks(s.chunks_indexed)
        if (s.status === 'done') {
          clearInterval(pollRef.current!)
          setState((prev) =>
            prev.status === 'processing'
              ? { status: 'done', result: { ...prev.result, chunks_indexed: s.chunks_indexed } }
              : prev,
          )
        } else if (s.status === 'error') {
          clearInterval(pollRef.current!)
          setState({ status: 'error', message: 'Falha na indexação em background.' })
        }
      } catch {
        // silencia erros de rede durante polling
      }
    }, 3000)

    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [state.status])

  async function handleSubmit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!file) return
    setState({ status: 'uploading' })
    try {
      const result = await ingestAuto(file, title || undefined, editor || undefined, translator || undefined)
      setChunks(0)
      setState({ status: 'processing', result })
      setFile(null)
      setTitle('')
      setEditor('')
      setTranslator('')
      if (inputRef.current) inputRef.current.value = ''
    } catch (err) {
      setState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Erro desconhecido',
      })
    }
  }

  function reset() {
    setState({ status: 'idle' })
    setFile(null)
    setTitle('')
    setEditor('')
    setTranslator('')
    setChunks(0)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* File picker */}
        <div>
          <label className="block text-sm text-texto-secundario mb-1.5">
            Arquivo PDF
          </label>
          <label className="flex items-center gap-3 cursor-pointer rounded-lg border border-dashed border-fundo-borda bg-fundo-card px-4 py-5 hover:border-dourado/40 transition-colors">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              className="w-5 h-5 shrink-0 text-texto-terciario"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"
              />
            </svg>
            <div className="min-w-0">
              {file ? (
                <p className="text-sm text-texto truncate">{file.name}</p>
              ) : (
                <p className="text-sm text-texto-terciario">
                  Clique para selecionar um PDF
                </p>
              )}
            </div>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
        </div>

        {/* Title override */}
        <div>
          <label className="block text-sm text-texto-secundario mb-1.5">
            Título{' '}
            <span className="text-texto-terciario font-normal">(opcional)</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="O backend detecta automaticamente"
            className="w-full rounded-lg border border-fundo-borda bg-fundo-card px-3 py-2.5 text-sm text-texto placeholder:text-texto-terciario focus:outline-none focus:border-dourado/50"
          />
        </div>

        {/* Editor e Tradutor */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm text-texto-secundario mb-1.5">
              Editor{' '}
              <span className="text-texto-terciario font-normal">(opcional)</span>
            </label>
            <input
              type="text"
              value={editor}
              onChange={(e) => setEditor(e.target.value)}
              placeholder="Ex: Paulus"
              className="w-full rounded-lg border border-fundo-borda bg-fundo-card px-3 py-2.5 text-sm text-texto placeholder:text-texto-terciario focus:outline-none focus:border-dourado/50"
            />
          </div>
          <div>
            <label className="block text-sm text-texto-secundario mb-1.5">
              Tradutor{' '}
              <span className="text-texto-terciario font-normal">(opcional)</span>
            </label>
            <input
              type="text"
              value={translator}
              onChange={(e) => setTranslator(e.target.value)}
              placeholder="Ex: Lourenço Costa"
              className="w-full rounded-lg border border-fundo-borda bg-fundo-card px-3 py-2.5 text-sm text-texto placeholder:text-texto-terciario focus:outline-none focus:border-dourado/50"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={!file || state.status === 'uploading' || state.status === 'processing'}
          className="w-full rounded-lg bg-dourado/90 hover:bg-dourado disabled:opacity-40 disabled:cursor-not-allowed px-4 py-3 text-sm font-semibold text-fundo transition-colors"
        >
          {state.status === 'uploading' ? 'Enviando...' : 'Enviar PDF'}
        </button>
      </form>

      {/* Processing — polling ativo */}
      {state.status === 'processing' && (
        <div className="rounded-lg border border-dourado/20 bg-fundo-card p-5 space-y-4">
          <div className="flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-dourado animate-pulse" />
            <p className="text-sm font-medium text-dourado">Indexando em segundo plano</p>
          </div>

          <MetaGrid result={state.result} />

          <div className="pt-1 border-t border-fundo-borda">
            <p className="text-xs text-texto-terciario">
              Trechos indexados até agora:{' '}
              <span className="text-texto font-medium">{chunks}</span>
            </p>
            <p className="text-xs text-texto-terciario/60 mt-0.5">
              OCR de PDFs grandes pode levar vários minutos. Pode fechar esta página.
            </p>
          </div>
        </div>
      )}

      {/* Done */}
      {state.status === 'done' && (
        <div className="rounded-lg border border-green-800/40 bg-green-900/10 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-green-400">Indexado com sucesso</p>
            <button
              onClick={reset}
              className="text-xs text-texto-terciario hover:text-texto transition-colors"
            >
              Enviar outro
            </button>
          </div>
          <MetaGrid result={state.result} />
          <Row
            label="Trechos indexados"
            value={String(state.result.chunks_indexed)}
            highlight
          />
        </div>
      )}

      {/* Error */}
      {state.status === 'error' && (
        <div className="rounded-lg border border-red-800/40 bg-red-900/10 p-4 space-y-2">
          <p className="text-sm font-semibold text-red-400">Erro no upload</p>
          <p className="text-xs text-red-300/80 font-mono leading-relaxed">
            {state.message}
          </p>
          <button
            onClick={reset}
            className="text-xs text-texto-terciario hover:text-texto transition-colors"
          >
            Tentar novamente
          </button>
        </div>
      )}
    </div>
  )
}

function MetaGrid({ result }: { result: AutoIngestResult }) {
  return (
    <div className="space-y-2">
      <Row label="Título" value={result.title} />
      <Row
        label="Autor"
        value={
          result.canonical_author
            ? result.canonical_author
            : `${result.author} (não reconhecido)`
        }
        highlight={!!result.canonical_author}
      />
      <Row label="Coleção" value={result.collection ?? '—'} />
      <Row label="Idioma" value={formatLanguage(result.language)} />
      {result.patristic_tradition && (
        <Row
          label="Tradição"
          value={
            { latina: 'Latina', grega: 'Grega', oriental: 'Oriental' }[
              result.patristic_tradition
            ] ?? result.patristic_tradition
          }
        />
      )}
      {result.library_section && (
        <Row
          label="Seção"
          value={
            { patristica: 'Patrística', documentos: 'Documentos da Igreja' }[
              result.library_section
            ] ?? result.library_section
          }
        />
      )}
    </div>
  )
}

function Row({
  label,
  value,
  highlight = false,
}: {
  label: string
  value: string
  highlight?: boolean
}) {
  return (
    <div className="flex items-start justify-between gap-4 text-sm">
      <span className="text-texto-terciario shrink-0">{label}</span>
      <span className={`text-right ${highlight ? 'text-dourado font-medium' : 'text-texto-secundario'}`}>
        {value}
      </span>
    </div>
  )
}
