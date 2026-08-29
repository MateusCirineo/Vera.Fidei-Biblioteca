'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { fetchWithTimeout } from '@/lib/http'
import { getPublicApiBase } from '@/lib/api-base'

const API_BASE = getPublicApiBase()
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? ''
const HEARTBEAT_MS = 60_000
const ANALYTICS_TIMEOUT_MS = 8_000

function send(path: string, event: 'view' | 'heartbeat') {
  if (path === '/admin' || path.startsWith('/admin/')) return
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (API_KEY) headers['X-API-Key'] = API_KEY
  void fetchWithTimeout(`${API_BASE}/analytics/event`, {
    method: 'POST',
    headers,
    credentials: 'include',
    keepalive: true,
    body: JSON.stringify({ path, event }),
  }, {
    timeoutMs: ANALYTICS_TIMEOUT_MS,
    timeoutMessage: 'A telemetria demorou demais.',
  }).then((response) => response.text()).catch(() => undefined)
}

export default function SiteAnalytics() {
  const pathname = usePathname()

  useEffect(() => {
    if (!pathname || pathname === '/admin' || pathname.startsWith('/admin/')) return
    send(pathname, 'view')

    const heartbeat = window.setInterval(() => {
      if (document.visibilityState === 'visible') send(pathname, 'heartbeat')
    }, HEARTBEAT_MS)

    return () => window.clearInterval(heartbeat)
  }, [pathname])

  return null
}
