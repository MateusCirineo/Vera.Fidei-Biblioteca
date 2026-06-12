'use client'

import { useEffect, useRef, useState } from 'react'

export default function AppSplash() {
  const [visible, setVisible] = useState(true)
  const [leaving, setLeaving] = useState(false)
  const releasedRef = useRef(false)

  useEffect(() => {
    const startedAt = performance.now()
    const timers: number[] = []

    const release = () => {
      if (releasedRef.current) {
        return
      }

      releasedRef.current = true
      const elapsed = performance.now() - startedAt
      const delay = Math.max(450, 1250 - elapsed)

      timers.push(
        window.setTimeout(() => {
          setLeaving(true)
          timers.push(window.setTimeout(() => setVisible(false), 560))
        }, delay),
      )
    }

    if (document.readyState === 'complete') {
      release()
    } else {
      window.addEventListener('load', release, { once: true })
      timers.push(window.setTimeout(release, 2600))
    }

    return () => {
      window.removeEventListener('load', release)
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [])

  if (!visible) {
    return null
  }

  return (
    <div
      className={`vf-app-splash${leaving ? ' vf-app-splash--leaving' : ''}`}
      role="status"
      aria-label="Inicializando Vera.Fidei"
      aria-live="polite"
    >
      <img
        src="/branding/splash-preto-1290x2796.png"
        alt=""
        className="vf-app-splash__art"
        aria-hidden="true"
      />
      <div className="vf-app-splash__shade" aria-hidden="true" />
      <div className="vf-app-splash__loader" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </div>
  )
}
