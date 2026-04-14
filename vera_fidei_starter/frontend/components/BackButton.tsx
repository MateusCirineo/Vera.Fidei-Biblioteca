'use client'

import { useRouter } from 'next/navigation'

export default function BackButton() {
  const router = useRouter()
  return (
    <button
      onClick={() => router.back()}
      className="text-sm text-texto-secundario hover:text-texto transition-colors"
    >
      ← Voltar
    </button>
  )
}
