'use client'

import { useEffect, useState, useCallback } from 'react'
import { isBookOffline, saveBookOffline, removeBookOffline } from '@/lib/offlineBooks'
import { getPublicApiBase } from '@/lib/api-base'

const API_BASE = getPublicApiBase()
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? ''

type Status = 'idle' | 'saving' | 'done' | 'error'

export default function SaveOfflineButton({
  bookId,
  title,
}: {
  bookId: number
  title: string
}) {
  const [offline, setOffline] = useState(false)
  const [status, setStatus] = useState<Status>('idle')

  useEffect(() => {
    isBookOffline(bookId).then(setOffline)
  }, [bookId])

  const toggle = useCallback(async () => {
    if (status === 'saving') return
    try {
      if (offline) {
        await removeBookOffline(bookId)
        setOffline(false)
      } else {
        setStatus('saving')
        await saveBookOffline(bookId, API_BASE, API_KEY)
        setOffline(true)
        setStatus('done')
        setTimeout(() => setStatus('idle'), 2500)
      }
    } catch {
      setStatus('error')
      setTimeout(() => setStatus('idle'), 3000)
    }
  }, [bookId, offline, status])

  const busy = status === 'saving'

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={busy}
      aria-label={`${offline ? 'Remover trechos offline de' : 'Salvar trechos offline de'} ${title}`}
      className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
        status === 'error'
          ? 'border-red-500/40 bg-red-500/10 text-red-400'
          : status === 'done'
          ? 'border-green-600/40 bg-green-600/10 text-green-400'
          : offline
          ? 'border-dourado/40 bg-dourado/10 text-dourado hover:bg-dourado/20'
          : 'border-fundo-borda bg-fundo-card text-texto-secundario hover:border-dourado/30 hover:text-texto'
      }`}
    >
      {busy ? (
        <>
          <span className="animate-spin text-sm leading-none">↻</span>
          Salvando trechos…
        </>
      ) : status === 'error' ? (
        'Erro — tente novamente'
      ) : status === 'done' ? (
        <>
          <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
            <path fillRule="evenodd" d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm11.78-1.72a.75.75 0 0 0-1.06-1.06L7 8.94 5.28 7.22a.75.75 0 0 0-1.06 1.06l2.25 2.25a.75.75 0 0 0 1.06 0l4.25-4.25Z" clipRule="evenodd" />
          </svg>
          Trechos salvos!
        </>
      ) : offline ? (
        <>
          <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
            <path fillRule="evenodd" d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm11.78-1.72a.75.75 0 0 0-1.06-1.06L7 8.94 5.28 7.22a.75.75 0 0 0-1.06 1.06l2.25 2.25a.75.75 0 0 0 1.06 0l4.25-4.25Z" clipRule="evenodd" />
          </svg>
          Disponível offline · remover
        </>
      ) : (
        <>
          <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
            <path d="M8.75 2.75a.75.75 0 0 0-1.5 0v5.69L5.03 6.22a.75.75 0 0 0-1.06 1.06l3.5 3.5a.75.75 0 0 0 1.06 0l3.5-3.5a.75.75 0 0 0-1.06-1.06L8.75 8.44V2.75Z" />
            <path d="M3.5 9.75a.75.75 0 0 0-1.5 0v1.5A2.75 2.75 0 0 0 4.75 14h6.5A2.75 2.75 0 0 0 14 11.25v-1.5a.75.75 0 0 0-1.5 0v1.5c0 .69-.56 1.25-1.25 1.25h-6.5c-.69 0-1.25-.56-1.25-1.25v-1.5Z" />
          </svg>
          Salvar trechos offline
        </>
      )}
    </button>
  )
}
