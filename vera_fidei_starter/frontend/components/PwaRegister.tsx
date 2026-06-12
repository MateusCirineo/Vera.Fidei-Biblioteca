'use client'

import { useEffect } from 'react'

export default function PwaRegister() {
  useEffect(() => {
    if (!('serviceWorker' in navigator)) {
      return
    }

    navigator.serviceWorker.register('/sw.js').catch(() => {
      // O PWA nao deve interromper a experiencia caso o navegador recuse o registro.
    })
  }, [])

  return null
}
