'use client'

import { useState } from 'react'
import dynamic from 'next/dynamic'

const QRCodeSVG = dynamic(
  () => import('qrcode.react').then((mod) => mod.QRCodeSVG),
  { ssr: false }
)

const PIX_PAYLOAD =
  '00020126330014BR.GOV.BCB.PIX0111519939518145204000053039865802BR5925Mateus Gustavo Cirineo Va6009SAO PAULO62140510z1n6yqVO0y6304F40C'

export default function DonationModal() {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(PIX_PAYLOAD)
    setCopied(true)
    setTimeout(() => setCopied(false), 2500)
  }

  return (
    <>
      {/* Botão flutuante */}
      <button
        onClick={() => setOpen(true)}
        aria-label="Apoie o Vera.Fidei via Pix"
        className="fixed bottom-[5.5rem] right-4 z-40 flex items-center gap-1.5 rounded-full bg-dourado px-4 py-2 text-sm font-semibold text-fundo shadow-lg shadow-black/40 hover:bg-dourado-claro active:scale-95 transition-all"
      >
        <HeartIcon />
        APOIE
      </button>

      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/75 pb-[5.5rem] px-4"
          onClick={() => setOpen(false)}
        >
          {/* Modal */}
          <div
            className="w-full max-w-sm rounded-2xl border border-fundo-borda bg-fundo-card p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Cabeçalho */}
            <div className="mb-4 flex items-start justify-between">
              <div className="flex items-center gap-2">
                <HeartIcon className="text-dourado w-5 h-5" />
                <h2 className="text-xl text-texto">Apoie o Vera.Fidei</h2>
              </div>
              <button
                onClick={() => setOpen(false)}
                aria-label="Fechar"
                className="text-texto-terciario hover:text-texto transition-colors"
              >
                <XIcon />
              </button>
            </div>

            <p className="mb-5 text-center text-sm text-texto-secundario leading-relaxed">
              Sua contribuição mantém este acervo patrístico{' '}
              <span className="text-dourado">vivo e acessível</span> a todos.
            </p>

            {/* QR Code Pix */}
            <div className="mb-4 flex justify-center">
              <div className="rounded-xl bg-white p-3 shadow-inner">
                <QRCodeSVG
                  value={PIX_PAYLOAD}
                  size={200}
                  bgColor="#ffffff"
                  fgColor="#111111"
                  level="M"
                />
              </div>
            </div>

            {/* Botão copiar */}
            <button
              onClick={handleCopy}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-dourado/30 bg-vinho/20 py-3 text-sm font-medium text-dourado transition-all hover:bg-vinho/40 active:scale-[0.98]"
            >
              {copied ? <CheckIcon /> : <CopyIcon />}
              {copied ? 'Código copiado!' : 'Copiar código Pix (Copia e Cola)'}
            </button>

            <p className="mt-3 text-center text-xs text-texto-terciario">
              Escaneie o QR Code ou cole o código no seu app bancário
            </p>
          </div>
        </div>
      )}
    </>
  )
}

function HeartIcon({ className = 'w-4 h-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M11.645 20.91l-.007-.003-.022-.012a15.247 15.247 0 01-.383-.218 25.18 25.18 0 01-4.244-3.17C4.688 15.36 2.25 12.174 2.25 8.25 2.25 5.322 4.714 3 7.688 3A5.5 5.5 0 0112 5.052 5.5 5.5 0 0116.313 3c2.973 0 5.437 2.322 5.437 5.25 0 3.925-2.438 7.111-4.739 9.256a25.175 25.175 0 01-4.244 3.17 15.247 15.247 0 01-.383.219l-.022.012-.007.004-.003.001a.752.752 0 01-.704 0l-.003-.001z" />
    </svg>
  )
}

function XIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      className="w-5 h-5"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

function CopyIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      className="w-4 h-4"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184"
      />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      className="w-4 h-4"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  )
}
