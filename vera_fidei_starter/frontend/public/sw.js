const CACHE_NAME = 'vera-fidei-pwa-v15'
const APP_SHELL = [
  '/offline.html',
  '/icons/icon-192.png',
]
const NETWORK_TIMEOUT_MS = 10_000

async function fetchWithNetworkTimeout(request) {
  const controller = new AbortController()
  let timeoutId
  let timedOut = false
  const timeout = new Promise((_, reject) => {
    timeoutId = setTimeout(() => {
      timedOut = true
      controller.abort()
      reject(new Error('Tempo de rede excedido'))
    }, NETWORK_TIMEOUT_MS)
  })
  try {
    const response = await Promise.race([
      fetch(request, { signal: controller.signal }),
      timeout,
    ])

    // Navigation requests use redirect="manual" inside a service worker.
    // Rebuilding an opaque redirect throws and previously sent visits to `/`
    // (which redirects to `/apresentacao`) to the cached offline page.
    if (response.type === 'opaqueredirect') {
      return response
    }

    // fetch() termina nos cabeçalhos. Para navegação e assets do shell, o
    // corpo também precisa caber no prazo; caso contrário a PWA poderia ficar
    // indefinidamente em branco mesmo depois de receber HTTP 200.
    const body = await Promise.race([response.arrayBuffer(), timeout])
    return new Response(body, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    })
  } catch (error) {
    if (timedOut) throw new Error('Tempo de rede excedido')
    throw error
  } finally {
    if (timeoutId !== undefined) clearTimeout(timeoutId)
  }
}

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
    url.pathname.startsWith('/pdfs/') ||
    url.pathname.endsWith('.pdf') ||
    url.pathname.includes('pdf.worker')
  ) {
    return
  }

  event.respondWith(
    (async () => {
      if (request.mode === 'navigate') {
        try {
          return await fetchWithNetworkTimeout(request)
        } catch {
          return caches.match('/offline.html')
        }
      }

      const cached = await caches.match(request)

      try {
        const response = await fetchWithNetworkTimeout(request)

        if (
          response.ok &&
          ['style', 'script', 'image', 'font'].includes(request.destination)
        ) {
          const cache = await caches.open(CACHE_NAME)
          cache.put(request, response.clone())
        }

        return response
      } catch {
        if (cached) {
          return cached
        }

        return new Response('', { status: 504, statusText: 'Offline' })
      }
    })(),
  )
})
