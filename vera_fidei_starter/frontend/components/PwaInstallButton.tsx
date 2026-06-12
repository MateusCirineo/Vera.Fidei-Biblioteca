'use client'

import { useEffect, useState } from 'react'

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

function isStandalone() {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.matchMedia('(display-mode: fullscreen)').matches ||
    (window.navigator as Navigator & { standalone?: boolean }).standalone === true
  )
}

function isAppleMobile() {
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent)
}

export default function PwaInstallButton() {
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const [installed, setInstalled] = useState(false)
  const [showHint, setShowHint] = useState(false)
  const [appleMobile, setAppleMobile] = useState(false)

  useEffect(() => {
    setInstalled(isStandalone())
    setAppleMobile(isAppleMobile())

    function handleBeforeInstallPrompt(event: Event) {
      event.preventDefault()
      setInstallPrompt(event as BeforeInstallPromptEvent)
      setShowHint(false)
    }

    function handleInstalled() {
      setInstalled(true)
      setInstallPrompt(null)
      setShowHint(false)
    }

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.addEventListener('appinstalled', handleInstalled)

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
      window.removeEventListener('appinstalled', handleInstalled)
    }
  }, [])

  async function install() {
    if (installed) {
      return
    }

    if (!installPrompt) {
      setShowHint(true)
      return
    }

    await installPrompt.prompt()
    const choice = await installPrompt.userChoice
    if (choice.outcome === 'accepted') {
      setInstalled(true)
      setShowHint(false)
    } else {
      setShowHint(true)
    }
    setInstallPrompt(null)
  }

  if (installed) {
    return (
      <div className="rounded-lg border border-dourado/20 bg-dourado/5 px-4 py-3 text-left">
        <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
          App instalado
        </p>
        <p className="mt-1 text-sm leading-relaxed text-texto-secundario">
          O Vera.Fidei já está rodando como aplicativo neste dispositivo.
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-fundo-borda bg-fundo-card px-4 py-3 text-left">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
            PWA oficial
          </p>
          <p className="mt-1 text-sm leading-relaxed text-texto-secundario">
            Instale o Vera.Fidei no celular para abrir como app, sem depender de aba do navegador.
          </p>
        </div>
        <button
          type="button"
          onClick={install}
          className="inline-flex shrink-0 items-center justify-center rounded-lg border border-dourado/35 bg-vinho px-4 py-2.5 text-sm font-semibold text-texto transition-colors hover:bg-vinho-claro"
        >
          Instalar Vera.Fidei
        </button>
      </div>

      {showHint && (
        <p className="mt-3 border-t border-fundo-borda pt-3 text-xs leading-relaxed text-texto-terciario">
          {appleMobile
            ? 'No iPhone: toque em Compartilhar e escolha Adicionar à Tela de Início.'
            : 'Se o botão nativo não apareceu, abra o menu do navegador e escolha Instalar app ou Adicionar à tela inicial.'}
        </p>
      )}
    </div>
  )
}
