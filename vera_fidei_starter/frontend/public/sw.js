const CACHE_NAME = 'vera-fidei-pwa-v7'
const APP_SHELL = [
  '/apresentacao',
  '/biblioteca',
  '/verificador',
  '/santos',
  '/oracoes',
  '/offline.html',
  '/branding/Logo-VF.png',
  '/branding/Logo-VF-seal.png',
  '/branding/Logo-VF-wine.png',
  '/branding/splash-preto-1290x2796.png',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/icon-1024.png',
  '/icons/maskable-512.png',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .catch(() => undefined),
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
      ),
  )
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  const { request } = event

  if (request.method !== 'GET') {
    return
  }

  const url = new URL(request.url)

  if (url.origin !== self.location.origin) {
    return
  }

  if (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/visualizar/') ||
    url.pathname.startsWith('/viewer/') ||
    url.pathname.endsWith('.pdf') ||
    url.pathname.includes('pdf.worker')
  ) {
    return
  }

  event.respondWith(
    (async () => {
      const cached = await caches.match(request)

      try {
        const response = await fetch(request)

        if (
          response.ok &&
          ['document', 'style', 'script', 'image', 'font'].includes(request.destination)
        ) {
          const cache = await caches.open(CACHE_NAME)
          cache.put(request, response.clone())
        }

        return response
      } catch {
        if (cached) {
          return cached
        }

        if (request.mode === 'navigate') {
          return caches.match('/offline.html')
        }

        return new Response('', { status: 504, statusText: 'Offline' })
      }
    })(),
  )
})
